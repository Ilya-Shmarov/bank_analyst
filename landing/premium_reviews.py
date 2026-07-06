# -*- coding: utf-8 -*-
"""Отзывы о премиальном обслуживании Сбера: сбор, классификация, лендинг.

Источники (только Сбер: СберПремьер / СберПервый / Sber Private):
  - Sravni.ru — JSON-API списка отзывов (robots.txt разрешает /proxy-reviews);
  - Otzovik.com — страницы продуктов «Пакет услуг СберПремьер/СберПервый»;
  - premiumbanking.info — раздел «Оценки и отзывы» по Сберу.

Banki.ru не сканируется: robots.txt запрещает раздел отзывов — по принципам
проекта запрет уважается (см. README). vbr.ru отдаёт HTTP 401 (антибот),
irecommend.ru релевантных отзывов не имеет — оба помечаются в отчёте.

Классификация тем/тональности/диагностики — эвристическая (ключевые слова
+ рейтинг как прайор), тональность считается по теме внутри отзыва.
LLM-классификация не подключена (нет ключа API) — это явно указано в футере.

Комплаенс: авторов не деанонимизируем сверх публичного текста; каждый
источник имеет kill-switch `enabled` (юридический статус ToS — в `tos_note`);
модуль запускается только вручную (--build-premium-reviews), без cron.
"""

import html
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from scanner.fetch import USER_AGENT, Fetcher
from scanner.sources import REQUEST_PAUSE, REQUEST_TIMEOUT

SBER_SRAVNI_ID = "5bb4f767245bc22a520a609b"  # ПАО «Сбербанк» (alias sberbank-rossii)

# Kill-switch по источникам: enabled=False выключает сборщик без падения
# остального сервиса. tos_note — статус для юридической сверки.
REVIEW_SOURCES = {
    "sravni_ru": {
        "name": "Sravni.ru",
        "enabled": True,
        "tos_note": "robots.txt разрешает /proxy-reviews и страницы отзывов; "
                    "ToS публично не запрещает некоммерческое исследование",
    },
    "otzovik": {
        "name": "Otzovik.com",
        "enabled": True,
        "tos_note": "robots.txt разрешает страницы /reviews/; лимит — только "
                    "открытые тизеры отзывов",
    },
    "pbi_reviews": {
        "name": "premiumbanking.info",
        "enabled": True,
        "tos_note": "открытый раздел «Оценки и отзывы»; robots.txt не запрещает",
    },
}

# Источники, проверенные и недоступные, — показываются в отчёте честно.
UNAVAILABLE_SOURCES = [
    ("Banki.ru («Народный рейтинг»)", "robots.txt запрещает раздел отзывов — "
     "запрет уважается, обход не применяется"),
    ("Vbr.ru (Выбери.ру)", "HTTP 401 — антибот; не обходим"),
    ("iRecommend.ru", "релевантных отзывов о премиум-пакетах Сбера не найдено"),
]

OTZOVIK_PAGES = [
    "https://otzovik.com/reviews/paket_uslug_sberpremer/",
    "https://otzovik.com/reviews/paket_uslug_sberperviy_ot_sberbanka/",
    "https://otzovik.com/reviews/paket_uslug_sberperviy_russia_saransk/",
]
PBI_REVIEWS_URL = "https://premiumbanking.info/ocenki_i_otzyvy?bank=sber"

# Маркеры премиум-сегмента для фильтра Sravni (общебанковский поток отзывов).
# «Прайм/СберПрайм» и «ДомКлик Плюс» исключены сознательно: это подписки
# массового сегмента, а не премиальное обслуживание (проверено на выборке).
PREMIUM_MARKERS = re.compile(
    r"премьер|сбер\s*перв|пакет\s+«?перв|уровень\s+«?перв|тариф\s+«?перв"
    r"|private\s*bank|прайвет|приват-?банк"
    r"|консьерж|бизнес[\s-]?зал|премиальн\w*\s+(обслуживан|пакет|карт|уров)"
    r"|премиум[\s-]*(пакет|обслуживан|уров)",
    re.IGNORECASE,
)

# ---------- таксономия тем (фикс-список по наполнению пакетов) ----------

TOPICS = {
    "cashback": ("Кэшбэк «Спасибо»",
                 r"кэшбэк|кешбэк|спасибо|бонус\w*\s+сбер|баллы"),
    "lounge": ("Бизнес-залы", r"бизнес[\s-]?зал|lounge|mir\s*pass|аэропорт"),
    "concierge": ("Консьерж", r"консьерж|личн\w+ помощник|ассистент"),
    "deposits": ("Спец-условия по вкладам",
                 r"вклад|накопительн|ставк\w+|процент\w*\s+годовых|% годовых"),
    "ecosystem": ("Экосистемные привилегии",
                  r"сберпрайм|прайм|okko|звук|самокат|афиша|фитмост|fitmost|"
                  r"экосистем|подписк"),
    "replace_mechanics": ("Механика замены/начисления",
                          r"замен\w+ (опци|привилег)|не начисл|не зачисл|"
                          r"не подключ|списал|отключ|сгорел|аннулир"),
    "options_purchase": ("Докупка опций", r"докупк|докупить|выбор опци|опци\w+ (за|можно)"),
    "level_keep": ("Сохранение уровня",
                   r"сохран\w+ (уровн|статус)|слетел|понизил|порог|остат\w+ на счет"),
    "support": ("Поддержка / SLA",
                r"поддержк|менеджер|горячая линия|колл?-?центр|обращени|"
                r"ответ\w* (банк|не получ)|заявк|жалоб"),
}
TOPIC_OTHER = ("Другое", None)

NEG_CUES = re.compile(
    r"обман|ужас|навяз|не работает|отказ|хуже|разочаров|тягомотин|днище|"
    r"плохо|минус|мошен|украл|потерял|блокир|бесполезн|профанац|негатив|"
    r"не соответств|не отвеча|проблем|жалоб|не смог|невозможно|позор|кошмар",
    re.IGNORECASE)
POS_CUES = re.compile(
    r"отличн|доволен|довольна|нравится|хорошо|спасибо за|плюс\b|супер|"
    r"рекомендую|удобн|быстро|вежлив|благодар|прекрасн|неплох",
    re.IGNORECASE)

DIAGNOSIS_RULES = [
    ("механика", r"не работает|сбой|не начисл|не зачисл|списал|не подключ|"
                 r"ошибк|глюч|заблокир|не приход|слетел"),
    ("коммуникация", r"не предупред|не сообщ|навяз|обеща|ввели в заблужден|"
                     r"никто не (объясн|сказал)|не уведом|скрыт|мелким шрифтом"),
    ("ожидание-реальность", r"ожидал|на деле|оказалось|по факту|вместо|"
                            r"не соответств|громкое назван|называется|профанац"),
    ("продуктовый гэп", r"нет (опци|такси|залов)|мало|урезал|убрал|сократил|"
                        r"недостаточно|только один|ограничен"),
]


# ---------- сбор ----------

class _ApiClient:
    """GET с конвенциями проекта: честный UA, robots.txt, пауза 2.5 с."""

    def __init__(self):
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        self._robots = {}
        self._last_ts = 0.0

    def allowed(self, url: str) -> bool:
        import urllib.robotparser
        from urllib.parse import urlparse
        origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = self._session.get(origin + "/robots.txt",
                                         timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp = None
            except requests.RequestException:
                rp = None
            self._robots[origin] = rp
        rp = self._robots[origin]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def get(self, url: str, params: dict = None):
        if not self.allowed(url):
            raise PermissionError(f"robots.txt запрещает {url}")
        elapsed = time.monotonic() - self._last_ts
        if elapsed < REQUEST_PAUSE:
            time.sleep(REQUEST_PAUSE - elapsed)
        self._last_ts = time.monotonic()
        resp = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def collect_sravni(client: _ApiClient, scan_date: str, log) -> list:
    """Все отзывы о Сбере из API Sravni, отфильтрованные премиум-маркерами."""
    out, page = [], 0
    while True:
        resp = client.get("https://www.sravni.ru/proxy-reviews/reviews", {
            "filterBy": "withRates", "orderBy": "byDate",
            "pageIndex": page, "pageSize": 100,
            "reviewObjectId": SBER_SRAVNI_ID, "reviewObjectType": "banks",
            "newIds": "true",
        })
        items = resp.json().get("items", [])
        if not items:
            break
        for it in items:
            text = " ".join([it.get("title") or "", _strip_html(it.get("text"))])
            if not PREMIUM_MARKERS.search(text):
                continue
            out.append({
                "review_id": f"sravni_{it.get('id')}",
                "source": "sravni_ru",
                "url": ("https://www.sravni.ru/bank/sberbank-rossii/otzyvy/"
                        f"{it.get('id')}/"),
                "date": (it.get("date") or "")[:10],
                "rating": _to_int(it.get("rating")),
                "text_raw": text,
                "scan_date": scan_date,
            })
        log.info("  [sravni] страница %d — релевантных накоплено %d", page, len(out))
        page += 1
        if page > 80:  # предохранитель
            break
    return out


def collect_otzovik(fetcher: Fetcher, scan_date: str, log) -> list:
    out = []
    for page_url in OTZOVIK_PAGES:
        result = fetcher.fetch([page_url], f"otzovik_{page_url.rstrip('/').rsplit('/', 1)[-1]}",
                               scan_date)
        if result.status != "ok":
            log.warning("  [otzovik] %s — %s", page_url, result.status)
            continue
        soup = BeautifulSoup(result.html, "html.parser")
        for item in soup.find_all(attrs={"itemprop": "review"}):
            url_el = item.find("link", attrs={"itemprop": "url"})
            href = url_el["href"] if url_el else page_url
            date_el = item.find(class_="review-postdate")
            date_iso = (date_el.get("content") or "")[:10] if date_el else ""
            rating_el = item.find(class_="rating-score")
            title_el = item.find(class_="review-title")
            parts = [title_el.get_text(" ", strip=True) if title_el else ""]
            for cls, prefix in (("review-plus", "Достоинства: "),
                                ("review-minus", "Недостатки: "),
                                ("review-teaser", "")):
                el = item.find(class_=cls)
                if el:
                    parts.append(prefix + el.get_text(" ", strip=True))
            text = " ".join(p for p in parts if p)
            if not text:
                continue
            out.append({
                "review_id": "otzovik_" + re.sub(r"\W+", "_", href[-40:]),
                "source": "otzovik",
                "url": href,
                "date": date_iso,
                "rating": _to_int(rating_el.get_text(" ", strip=True))
                          if rating_el else None,
                "text_raw": text,
                "scan_date": scan_date,
            })
        log.info("  [otzovik] %s — всего накоплено %d", page_url, len(out))
    return out


def collect_pbi(fetcher: Fetcher, scan_date: str, log) -> list:
    result = fetcher.fetch([PBI_REVIEWS_URL], "pbi_reviews_sber", scan_date)
    if result.status != "ok":
        log.warning("  [pbi] %s — %s", PBI_REVIEWS_URL, result.status)
        return []
    soup = BeautifulSoup(result.html, "html.parser")
    out = []
    # Карточки отзывов содержат ссылку «Смотреть весь отзыв» (?review=NNN)
    seen = set()
    for a in soup.find_all("a", href=re.compile(r"ocenki_i_otzyvy\?review=\d+")):
        href = a["href"]
        if not href.startswith("http"):
            href = "https://premiumbanking.info/" + href.lstrip("/")
        rid = re.search(r"review=(\d+)", href).group(1)
        if rid in seen:
            continue
        seen.add(rid)
        card = a
        for _ in range(6):  # поднимаемся до карточки с текстом
            card = card.parent
            if card is None or len(card.get_text(strip=True)) > 120:
                break
        text = card.get_text(" ", strip=True) if card else ""
        text = re.sub(r"Смотреть весь отзыв.*$", "", text).strip()
        rating_m = re.search(r"\b(\d{1,2}[.,]\d)\b", text)
        out.append({
            "review_id": f"pbi_{rid}",
            "source": "pbi_reviews",
            "url": href,
            "date": "",  # ПБИ не публикует дату отзыва в листинге
            "rating": rating_m.group(1).replace(",", ".") if rating_m else None,
            "text_raw": text,
            "scan_date": scan_date,
        })
    log.info("  [pbi] найдено отзывов: %d", len(out))
    return out


def _to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


# ---------- классификация (эвристика) ----------

def classify(review: dict) -> dict:
    """Темы отзыва + тональность и диагностика по каждой теме отдельно."""
    text = review["text_raw"]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    topics = []
    for topic_id, (label, pattern) in TOPICS.items():
        hits = [s for s in sentences if re.search(pattern, s, re.IGNORECASE)]
        if not hits:
            continue
        topics.append(_topic_instance(topic_id, label, hits, review))
    if not topics:
        topics.append(_topic_instance("other", TOPIC_OTHER[0], sentences, review))
    return {**review, "topics": topics}


def _topic_instance(topic_id: str, label: str, sentences: list, review: dict) -> dict:
    ctx = " ".join(sentences)
    neg, pos = len(NEG_CUES.findall(ctx)), len(POS_CUES.findall(ctx))
    if neg > pos:
        sentiment = "neg"
    elif pos > neg:
        sentiment = "pos"
    else:  # прайор — оценка автора
        rating = review.get("rating")
        try:
            r = float(rating)
        except (TypeError, ValueError):
            r = None
        if r is not None and r > 5:  # шкала ПБИ 0–10 → 0–5
            r = r / 2
        if r is None:
            sentiment = "neu"
        elif r <= 2:
            sentiment = "neg"
        elif r >= 4:
            sentiment = "pos"
        else:
            sentiment = "neu"
    diagnosis, diag_hits = "не определено", 0
    for name, pattern in DIAGNOSIS_RULES:
        n = len(re.findall(pattern, ctx, re.IGNORECASE))
        if n > diag_hits:
            diagnosis, diag_hits = name, n
    confidence = min(0.9, 0.3 + 0.15 * (neg + pos + diag_hits))
    return {"topic_id": topic_id, "topic": label, "sentiment": sentiment,
            "diagnosis": diagnosis, "confidence": round(confidence, 2),
            "quote": ctx[:280]}


# ---------- хранение (тянем только новое) ----------

def load_store(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {"reviews": [], "runs": []}


def save_store(store: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False, indent=1)


# ---------- сборка лендинга ----------

def build_premium_reviews_landing(raw_dir: Path, store_path: Path,
                                  output_dir: Path, log) -> dict:
    scan_dt = datetime.now()
    scan_date = scan_dt.strftime("%Y-%m-%d")
    client = _ApiClient()
    fetcher = Fetcher(raw_dir)

    store = load_store(store_path)
    known_ids = {r["review_id"] for r in store["reviews"]}
    collected, failures = [], []

    collectors = {
        "sravni_ru": lambda: collect_sravni(client, scan_date, log),
        "otzovik": lambda: collect_otzovik(fetcher, scan_date, log),
        "pbi_reviews": lambda: collect_pbi(fetcher, scan_date, log),
    }
    for source_id, run in collectors.items():
        meta = REVIEW_SOURCES[source_id]
        if not meta["enabled"]:
            failures.append((meta["name"], "выключен (kill-switch)"))
            continue
        log.info("── %s", meta["name"])
        try:
            collected += run()
        except Exception as exc:  # noqa: BLE001 — источник не роняет сборку
            log.warning("  [fail] %s: %s", meta["name"], exc)
            failures.append((meta["name"], f"{type(exc).__name__}: {exc}"))

    new_reviews = [r for r in collected if r["review_id"] not in known_ids]
    store["reviews"].extend(classify(r) for r in new_reviews)
    # переклассифицировать старые записи без topics (миграция схемы)
    store["reviews"] = [r if r.get("topics") else classify(r)
                        for r in store["reviews"]]
    store["runs"].append({
        "date": scan_dt.isoformat(timespec="seconds"),
        "collected": len(collected), "new": len(new_reviews),
        "failed_sources": [f[0] for f in failures],
    })
    save_store(store, store_path)

    output_path = output_dir / f"premium_reviews_report_{scan_date}.html"
    html_text = render_html(store["reviews"], scan_dt, failures)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")
    return {"output": str(output_path), "total": len(store["reviews"]),
            "new": len(new_reviews), "failed": len(failures)}


# ---------- рендер ----------

def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def render_html(reviews: list, generated_at: datetime, failures: list) -> str:
    total = len(reviews)
    cutoff_12m = (generated_at - timedelta(days=365)).strftime("%Y-%m-%d")
    recent = [r for r in reviews if (r.get("date") or "") >= cutoff_12m]
    undated = [r for r in reviews if not r.get("date")]

    # агрегация по темам
    agg = {}
    for r in reviews:
        for t in r["topics"]:
            a = agg.setdefault(t["topic"], {"topic_id": t["topic_id"],
                                            "n": 0, "neg": 0, "pos": 0, "neu": 0,
                                            "diag": {}, "quotes": []})
            a["n"] += 1
            a[t["sentiment"]] += 1
            a["diag"][t["diagnosis"]] = a["diag"].get(t["diagnosis"], 0) + 1
            a["quotes"].append((t["sentiment"], t["quote"], r["url"],
                                r["source"], r.get("date", "")))
    topics_sorted = sorted(agg.items(), key=lambda kv: -kv[1]["n"])

    by_source = {}
    for r in reviews:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    source_names = {sid: meta["name"] for sid, meta in REVIEW_SOURCES.items()}

    topic_cards = "\n".join(_render_topic(name, a) for name, a in topics_sorted)
    source_rows = "\n".join(
        f"<tr><td>{_esc(source_names.get(sid, sid))}</td>"
        f"<td class='num'>{n}</td><td>доступен</td></tr>"
        for sid, n in sorted(by_source.items(), key=lambda kv: -kv[1]))
    source_rows += "\n" + "\n".join(
        f"<tr class='off'><td>{_esc(name)}</td><td class='num'>—</td>"
        f"<td>{_esc(why)}</td></tr>" for name, why in UNAVAILABLE_SOURCES)
    for name, why in failures:
        source_rows += (f"\n<tr class='off'><td>{_esc(name)}</td>"
                        f"<td class='num'>—</td><td>сбой: {_esc(why)}</td></tr>")

    recos = build_recommendations(topics_sorted)
    reco_cards = "\n".join(_render_reco(i + 1, r) for i, r in enumerate(recos))

    neg_total = sum(1 for r in reviews for t in r["topics"]
                    if t["sentiment"] == "neg")
    all_topics = sum(len(r["topics"]) for r in reviews)
    generated = generated_at.strftime("%d.%m.%Y %H:%M")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Отзывы о премиальном обслуживании Сбера</title>
  <style>{_CSS}</style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="eyebrow">СберПремьер · СберПервый · Sber Private</p>
      <h1>Отзывы о премиальном обслуживании</h1>
      <p class="lead">Открытые отзывы клиентов о премиальных пакетах Сбера,
      собранные с Sravni.ru, Otzovik.com и premiumbanking.info.
      Темы и тональность размечены по каждой теме внутри отзыва.</p>
      <div class="stats">
        <div><b>{total}</b><span>отзывов всего</span></div>
        <div><b>{len(recent)}</b><span>за последние 12 мес</span></div>
        <div><b>{len(undated)}</b><span>без даты (ПБИ)</span></div>
        <div><b class="neg-num">{neg_total}/{all_topics}</b><span>негативных тем</span></div>
      </div>
    </section>

    <section class="block">
      <h2>Темы</h2>
      <div class="grid">
{topic_cards}
      </div>
    </section>

    <section class="block">
      <h2>Источники</h2>
      <table class="sources">
        <tr><th>Источник</th><th>Отзывов</th><th>Статус</th></tr>
{source_rows}
      </table>
    </section>

    <section class="block">
      <h2>Рекомендации: что изменить, чтобы снизить поток негативных отзывов</h2>
      <p class="lead-small">Гипотезы построены из тем выше: берутся темы с
      {MIN_MENTIONS_FOR_RECO}+ упоминаниями и преобладанием негатива,
      приоритет — RICE (Reach из объёма упоминаний, Impact/Effort —
      экспертная оценка, Confidence занижен из-за смещения источника).
      Это гипотезы для проверки продуктовой командой, не готовые решения.</p>
      <div class="grid">
{reco_cards}
      </div>
    </section>

    <footer class="footer">
      <p><b>Сгенерировано:</b> {_esc(generated)} ·
         <b>Объём выборки:</b> {total} отзывов
         ({len(recent)} за последние 12 месяцев).</p>
      <p><b>Дисклеймер смещения:</b> сайты-отзовики — не репрезентативная
      выборка премиального сегмента: туда приходят преимущественно с жалобами,
      довольные клиенты почти не пишут. Доли негатива нельзя переносить на
      клиентскую базу. Banki.ru (крупнейший массив отзывов) недоступен:
      robots.txt запрещает сбор, запрет уважается.</p>
      <p><b>Метод:</b> классификация тем, тональности и типа проблемы —
      эвристическая (словари + оценка автора), LLM-разметка не применялась.
      Ручная валидация разметки не проводилась — трактовать как
      предварительную.</p>
    </footer>
  </main>
</body>
</html>"""


# ---------- рекомендации ----------
#
# Гипотезы изменений по темам с достаточным объёмом негатива. Impact/Effort —
# экспертная оценка (1–3), Confidence занижен из-за смещения источника
# (отзовики = преимущественно жалобы). Reach берётся из данных (упоминания).

RECO_TEMPLATES = {
    "support": {
        "hypothesis": "Ввести SLA на обращения премиум-клиентов: выделенная "
                      "линия, статус обращения в приложении, срок первого "
                      "ответа. Большая часть негатива — не сам продукт, а "
                      "невозможность быстро решить вопрос.",
        "impact": 3, "effort": 2,
    },
    "cashback": {
        "hypothesis": "Автоматизировать начисление компенсаций (рестораны, "
                      "такси) без ручных обращений: клиенты СберПервого "
                      "вынуждены писать обращение после каждой транзакции.",
        "impact": 3, "effort": 2,
    },
    "replace_mechanics": {
        "hypothesis": "Сделать механику продления/отключения пакета "
                      "прозрачной: явное подтверждение перед отключением "
                      "автопродления и возможность отменить действие — "
                      "клиенты теряют уровень по ошибочному нажатию.",
        "impact": 2, "effort": 1,
    },
    "ecosystem": {
        "hypothesis": "Расширить выбор опций пакета (сейчас «только один вид "
                      "можно выбрать») или дать докупку второй опции — "
                      "частая претензия при в целом позитивной оценке "
                      "наполнения.",
        "impact": 2, "effort": 2,
    },
    "level_keep": {
        "hypothesis": "Предупреждать о предстоящем понижении уровня заранее "
                      "(push + грейс-период), а не по факту списания "
                      "привилегий.",
        "impact": 2, "effort": 1,
    },
    "deposits": {
        "hypothesis": "Синхронизировать обещанные премиальные надбавки по "
                      "вкладам с фактическими условиями в приложении — "
                      "расхождение воспринимается как обман.",
        "impact": 2, "effort": 2,
    },
    "lounge": {
        "hypothesis": "Показывать остаток проходов в бизнес-залы и условия "
                      "их начисления в приложении до поездки.",
        "impact": 1, "effort": 1,
    },
    "concierge": {
        "hypothesis": "Зафиксировать сроки ответа консьержа и вернуть "
                      "клиенту статус запроса.",
        "impact": 1, "effort": 1,
    },
    "options_purchase": {
        "hypothesis": "Упростить докупку опций: цена и состав до "
                      "подключения, отмена в один шаг.",
        "impact": 1, "effort": 1,
    },
}

MIN_MENTIONS_FOR_RECO = 3  # темы с меньшим объёмом — шум, не основание


def build_recommendations(topics_sorted: list) -> list:
    """Формирует рекомендации из агрегатов тем: только темы с достаточным
    объёмом и преобладанием негатива, приоритет — RICE."""
    recos = []
    for name, a in topics_sorted:
        tpl = RECO_TEMPLATES.get(a["topic_id"])
        if tpl is None or a["n"] < MIN_MENTIONS_FOR_RECO or a["neg"] <= a["pos"]:
            continue
        diag = sorted(((k, v) for k, v in a["diag"].items()
                       if k != "не определено"), key=lambda kv: -kv[1])
        change_type = diag[0][0] if diag else "механика"
        reach = a["n"]
        neg_share = a["neg"] / a["n"]
        # Confidence: доля негатива по теме, но с потолком 0.6 —
        # источник смещён в сторону жалоб
        confidence = round(min(0.6, 0.2 + 0.4 * neg_share), 2)
        score = round(reach * tpl["impact"] * confidence / tpl["effort"], 1)
        recos.append({
            "topic": name, "hypothesis": tpl["hypothesis"],
            "type": change_type, "reach": reach,
            "impact": tpl["impact"], "confidence": confidence,
            "effort": tpl["effort"], "score": score,
            "neg_share": round(100 * neg_share),
        })
    return sorted(recos, key=lambda r: -r["score"])


def _render_reco(i: int, r: dict) -> str:
    return f"""      <article class="card reco">
        <div class="card-head">
          <h3><span class="rank">{i}</span> {_esc(r['topic'])}</h3>
          <span class="count">RICE {r['score']}</span>
        </div>
        <p class="hypothesis">{_esc(r['hypothesis'])}</p>
        <p class="meta">тип изменения: <b>{_esc(r['type'])}</b> ·
           упоминаний: <b>{r['reach']}</b> ·
           негатива в теме: <b class="neg-num">{r['neg_share']}%</b></p>
        <p class="meta rice">Reach {r['reach']} × Impact {r['impact']} ×
           Confidence {r['confidence']} / Effort {r['effort']}
           = {r['score']}</p>
      </article>"""


_SENT_LABEL = {"neg": "негатив", "pos": "позитив", "neu": "нейтрально"}


def _render_topic(name: str, a: dict) -> str:
    n = a["n"]
    neg_share = round(100 * a["neg"] / n) if n else 0
    diag = sorted(a["diag"].items(), key=lambda kv: -kv[1])
    diag_str = ", ".join(f"{k} ×{v}" for k, v in diag[:3] if k != "не определено")
    quotes = sorted(a["quotes"], key=lambda q: q[0] != "neg")[:3]
    quotes_html = "\n".join(
        f"""<blockquote class="q {q[0]}">
          <span class="sent {q[0]}">{_SENT_LABEL[q[0]]}</span>
          {_esc(q[1])}
          <a href="{_esc(q[2])}" target="_blank" rel="noreferrer">источник ({_esc(q[4] or 'дата не указана')})</a>
        </blockquote>""" for q in quotes)
    bar = (f'<div class="bar"><i style="width:{neg_share}%"></i></div>'
           if n else "")
    return f"""      <article class="card">
        <div class="card-head">
          <h3>{_esc(name)}</h3>
          <span class="count">{n} упомин.</span>
        </div>
        <p class="meta">негатив <b class="neg-num">{a['neg']}</b> ·
           позитив <b>{a['pos']}</b> · нейтрально {a['neu']}
           <span class="negshare">{neg_share}% негатива</span></p>
        {bar}
        <p class="meta">{_esc('Диагностика: ' + diag_str) if diag_str else ''}</p>
        {quotes_html}
      </article>"""


_CSS = """
:root {
  --bg: #FFFFFF;
  --card: #FAFAF8;
  --ink: #1A1D1B;
  --muted: #64746b;
  --line: #E7E5DE;
  --green: #188f4f;
  --green-soft: #188f4f1a;
  --neg: #B3492F;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.page { max-width: 1160px; margin: 0 auto; padding: 36px 18px 56px; }
.hero { padding: 18px 0 28px; border-bottom: 1px solid var(--line); }
.eyebrow { margin: 0 0 8px; color: var(--green); font-size: 13px;
  font-weight: 700; text-transform: uppercase; }
h1 { margin: 0; font-size: 42px; line-height: 1.08; }
.lead { max-width: 780px; margin: 14px 0 0; color: var(--muted); font-size: 17px; }
.stats { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }
.stats div { min-width: 150px; background: var(--card);
  border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; }
.stats b { display: block; font-size: 24px; color: var(--green);
  font-family: ui-monospace, "SF Mono", Menlo, monospace; }
.stats b.neg-num { color: var(--neg); }
.stats span { color: var(--muted); font-size: 13px; }
.block { margin-top: 34px; }
h2 { margin: 0 0 16px; font-size: 26px; }
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.card { background: var(--card); border: 1px solid var(--line);
  border-radius: 8px; padding: 18px; }
.card-head { display: flex; justify-content: space-between; align-items: baseline; }
h3 { margin: 0; font-size: 19px; }
.count { background: var(--green-soft); color: var(--green); border-radius: 999px;
  padding: 2px 10px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.meta { color: var(--muted); font-size: 13px; margin: 8px 0 0; }
.meta b { font-family: ui-monospace, "SF Mono", Menlo, monospace; color: var(--ink); }
.meta b.neg-num, .negshare { color: var(--neg); }
.negshare { float: right; font-weight: 700;
  font-family: ui-monospace, "SF Mono", Menlo, monospace; }
.bar { height: 4px; background: var(--green-soft); border-radius: 2px;
  margin-top: 8px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--neg); }
blockquote.q { margin: 12px 0 0; padding: 10px 12px; border-left: 3px solid var(--green);
  background: var(--bg); border-radius: 0 6px 6px 0; font-size: 14px; }
blockquote.q.neg { border-left-color: var(--neg); }
.sent { display: inline-block; margin-right: 6px; border-radius: 999px;
  padding: 1px 8px; font-size: 11px; font-weight: 700;
  background: var(--green-soft); color: var(--green); }
.sent.neg { background: #B3492F1a; color: var(--neg); }
blockquote.q a { display: block; margin-top: 6px; color: var(--muted);
  font-size: 12px; }
.lead-small { max-width: 860px; margin: -6px 0 16px; color: var(--muted);
  font-size: 14px; }
.card.reco { border-top: 3px solid var(--green); }
.rank { display: inline-block; min-width: 24px; height: 24px; line-height: 24px;
  text-align: center; background: var(--green); color: #fff; border-radius: 999px;
  font-size: 13px; font-family: ui-monospace, "SF Mono", Menlo, monospace; }
.hypothesis { margin: 10px 0 0; font-size: 15px; }
.meta.rice { font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 12px; }
table.sources { width: 100%; border-collapse: collapse; }
.sources th, .sources td { text-align: left; padding: 8px 10px;
  border-bottom: 1px solid var(--line); font-size: 14px; }
.sources th { color: var(--muted); font-size: 12px; text-transform: uppercase; }
.sources td.num { font-family: ui-monospace, "SF Mono", Menlo, monospace; }
.sources tr.off td { color: var(--muted); }
.footer { margin-top: 40px; padding-top: 18px; border-top: 1px solid var(--line);
  color: var(--muted); font-size: 13px; }
.footer p { margin: 6px 0; }
@media (max-width: 820px) {
  h1 { font-size: 32px; }
  .grid { grid-template-columns: 1fr; }
}
"""
