# -*- coding: utf-8 -*-
"""
Получение контента страниц.

Основной путь — requests. Если страница отдаёт заглушку без контента
(JS-рендеринг), пробуем fallback на Playwright, если он установлен.
Уважаем robots.txt, держим паузу между запросами, при недоступности
источника не падаем — возвращаем FetchResult со статусом ошибки.
"""

import logging
import time
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import requests

from scanner.sources import REQUEST_PAUSE, REQUEST_TIMEOUT

log = logging.getLogger("scanner.fetch")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 "
    "competitor-scanner/1.0 (research; contact via repo)"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5",
}

# Минимальная длина видимого текста, ниже которой считаем,
# что страница требует JS-рендеринга
MIN_TEXT_LENGTH = 500


@dataclass
class FetchResult:
    url: str
    status: str  # ok | error | blocked_robots | unavailable | js_required
    html: str = ""
    error: str = ""
    fetched_via: str = "requests"  # requests | playwright
    tried_urls: list = field(default_factory=list)


class Fetcher:
    def __init__(self, raw_dir: Path, pause: float = REQUEST_PAUSE):
        self.raw_dir = raw_dir
        self.pause = pause
        self._robots_cache = {}
        self._url_cache = {}  # url -> FetchResult: общие страницы качаем 1 раз за скан
        self._last_request_ts = 0.0
        self._session = requests.Session()
        self._session.headers.update(HEADERS)

    # ---------- robots.txt ----------

    def _robots_allows(self, url: str) -> bool:
        origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if origin not in self._robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = self._session.get(
                    origin + "/robots.txt", timeout=REQUEST_TIMEOUT
                )
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp = None  # нет robots.txt — считаем, что можно
            except requests.RequestException:
                rp = None
            self._robots_cache[origin] = rp
        rp = self._robots_cache[origin]
        if rp is None:
            return True
        return rp.can_fetch(USER_AGENT, url)

    # ---------- rate limiting ----------

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request_ts
        if elapsed < self.pause:
            time.sleep(self.pause - elapsed)
        self._last_request_ts = time.monotonic()

    # ---------- основной fetch ----------

    def fetch(self, urls: list, source_id: str, scan_date: str) -> FetchResult:
        """Пробует candidate-URL по порядку до первого успешного.
        Если все URL отдали блокировку (403/429/498 или сброс соединения),
        делает второй проход через Playwright — рендер как обычный браузер,
        без обхода капчи. Успешные URL кэшируются на время скана."""
        for url in urls:
            if url in self._url_cache:
                cached = self._url_cache[url]
                log.info("  [cache] %s", url)
                return cached
        result = self._fetch_via_requests(urls, source_id, scan_date)
        if result.status == "unavailable":
            pw_result = self._fetch_via_playwright_pass(urls, source_id, scan_date,
                                                        result.tried_urls)
            if pw_result is not None:
                result = pw_result
        if result.status == "ok":
            self._url_cache[result.url] = result
        return result

    def _fetch_via_requests(self, urls: list, source_id: str,
                            scan_date: str) -> FetchResult:
        last_error = ""
        tried = []
        for url in urls:
            tried.append(url)
            if not self._robots_allows(url):
                log.warning("  [robots] %s запрещён robots.txt — пропускаю", url)
                last_error = "запрещено robots.txt"
                continue

            self._throttle()
            try:
                resp = self._session.get(
                    url, timeout=REQUEST_TIMEOUT, allow_redirects=True
                )
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                log.warning("  [error] %s — %s", url, last_error)
                continue

            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}"
                log.warning("  [http %s] %s", resp.status_code, url)
                continue

            html = resp.text
            if _looks_js_rendered(html):
                pw_html = self._try_playwright(url)
                if pw_html:
                    result = FetchResult(url=url, status="ok", html=pw_html,
                                         fetched_via="playwright", tried_urls=tried)
                    self._save_raw(result, source_id, scan_date)
                    return result
                last_error = "страница требует JS-рендеринга (playwright недоступен)"
                log.warning("  [js] %s — %s", url, last_error)
                result = FetchResult(url=url, status="js_required", html=html,
                                     error=last_error, tried_urls=tried)
                self._save_raw(result, source_id, scan_date)
                return result

            result = FetchResult(url=url, status="ok", html=html, tried_urls=tried)
            self._save_raw(result, source_id, scan_date)
            return result

        status = "blocked_robots" if last_error == "запрещено robots.txt" else "unavailable"
        return FetchResult(url=urls[0] if urls else "", status=status,
                           error=last_error or "нет URL", tried_urls=tried)

    def _fetch_via_playwright_pass(self, urls: list, source_id: str,
                                   scan_date: str, tried: list):
        """Второй проход по URL через Playwright после блокировки requests.
        Возвращает FetchResult при успехе, None — если не помогло."""
        for url in urls:
            if not self._robots_allows(url):
                continue
            self._throttle()
            html = self._try_playwright(url)
            if not html:
                return None  # playwright недоступен или упал — дальше нет смысла
            if _looks_captcha(html):
                log.warning("  [antibot] %s отдаёт капчу/челлендж — не обходим, "
                            "помечаю недоступным", url)
                continue
            if _looks_js_rendered(html):
                continue
            result = FetchResult(url=url, status="ok", html=html,
                                 fetched_via="playwright", tried_urls=tried)
            self._save_raw(result, source_id, scan_date)
            return result
        return None

    # ---------- playwright fallback ----------

    def _try_playwright(self, url: str):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            log.info("  [js] playwright не установлен — JS-fallback пропущен "
                     "(pip install playwright && playwright install chromium)")
            return None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(url, timeout=REQUEST_TIMEOUT * 1000,
                          wait_until="networkidle")
                html = page.content()
                browser.close()
                log.info("  [js] %s получен через playwright", url)
                return html
        except Exception as exc:  # noqa: BLE001 — любой сбой браузера не должен ронять скан
            log.warning("  [js] playwright не справился с %s: %s", url, exc)
            return None

    # ---------- raw-архив ----------

    def _save_raw(self, result: FetchResult, source_id: str, scan_date: str):
        if not result.html:
            return
        day_dir = self.raw_dir / scan_date
        day_dir.mkdir(parents=True, exist_ok=True)
        path = day_dir / f"{source_id}.html"
        path.write_text(result.html, encoding="utf-8", errors="ignore")


def _looks_captcha(html: str) -> bool:
    """Маркеры капчи/антибот-челленджа: такие страницы не обходим."""
    lowered = html.lower()
    markers = ["captcha", "капча", "antibot", "антибот",
               "checking your browser", "доступ ограничен", "access denied",
               "подтвердите, что вы не робот", "are you a robot"]
    return any(m in lowered for m in markers)


def _looks_js_rendered(html: str) -> bool:
    """Эвристика: почти пустой текст или явные маркеры SPA-заглушки."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    if len(text) >= MIN_TEXT_LENGTH:
        return False
    markers = ["включите javascript", "enable javascript", "loading...",
               "требуется javascript"]
    lowered = html.lower()
    return len(text) < MIN_TEXT_LENGTH or any(m in lowered for m in markers)
