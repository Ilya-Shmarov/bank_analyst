# -*- coding: utf-8 -*-
"""Static premium program news feed built from PremiumBanking.info updates."""

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib import robotparser

import requests
from bs4 import BeautifulSoup, Tag

from scanner.sources import PRIORITY_SOURCE_URLS


USER_AGENT = "bank-analyst-premium-updates/1.0"
PBI_UPDATE_SOURCES = [
    {"bank": "Сбер", "url": "https://premiumbanking.info/sber"},
    {"bank": "Альфа-Банк", "url": "https://premiumbanking.info/alfabank"},
    {"bank": "ВТБ", "url": "https://premiumbanking.info/vtb"},
    {"bank": "Газпромбанк", "url": "https://premiumbanking.info/gazprombank"},
    {"bank": "Озон Банк", "url": "https://premiumbanking.info/ozon"},
    {"bank": "Райффайзен Банк", "url": "https://premiumbanking.info/raiffeisen"},
    {"bank": "Т-Банк", "url": "https://premiumbanking.info/tbank"},
]
SOURCE_BUTTON_URLS = {
    "Сбер": PRIORITY_SOURCE_URLS["official"]["sber_premium"],
    "Альфа-Банк": PRIORITY_SOURCE_URLS["official"]["alfa_only"],
    "ВТБ": PRIORITY_SOURCE_URLS["official"]["vtb_privilege"],
    "Газпромбанк": PRIORITY_SOURCE_URLS["official"]["gazprombank"],
    "Озон Банк": PRIORITY_SOURCE_URLS["official"]["ozon_ultra"],
    "Райффайзен Банк": PRIORITY_SOURCE_URLS["official"]["raiffeisen"],
    "Т-Банк": PRIORITY_SOURCE_URLS["official"]["tbank_premium"],
}
MONTHS = {
    "янв": "01",
    "январь": "01",
    "января": "01",
    "фев": "02",
    "февраль": "02",
    "февраля": "02",
    "мар": "03",
    "март": "03",
    "марта": "03",
    "апр": "04",
    "апрель": "04",
    "апреля": "04",
    "май": "05",
    "мая": "05",
    "июн": "06",
    "июнь": "06",
    "июня": "06",
    "июл": "07",
    "июль": "07",
    "июля": "07",
    "авг": "08",
    "август": "08",
    "августа": "08",
    "сен": "09",
    "сент": "09",
    "сентябрь": "09",
    "сентября": "09",
    "окт": "10",
    "октябрь": "10",
    "октября": "10",
    "ноя": "11",
    "ноябрь": "11",
    "ноября": "11",
    "дек": "12",
    "декабрь": "12",
    "декабря": "12",
}


def build_premium_changes_landing(_workbook_path: Path, output_path: Path) -> dict:
    """Fetch PremiumBanking.info update blocks and write a static HTML page."""
    changes, failed = fetch_pbi_updates()
    banks = group_by_bank(changes)
    html_text = render_html(banks, datetime.now())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")
    return {
        "output": str(output_path),
        "banks": len(banks),
        "changes": sum(len(bank["changes"]) for bank in banks),
        "failed": failed,
    }


def load_changes(_workbook_path: Path = None) -> list[dict]:
    """Return news records from PremiumBanking.info update sections.

    The argument is accepted for compatibility with the main comparison builder;
    the comparison data itself is not used as a source for this feed.
    """
    changes, _failed = fetch_pbi_updates()
    return changes


def fetch_pbi_updates(fetcher=None) -> tuple[list[dict], int]:
    changes = []
    failed = 0
    for source in PBI_UPDATE_SOURCES:
        try:
            page_html = fetcher(source["url"]) if fetcher else _fetch_pbi_page(source["url"])
            changes.extend(parse_pbi_updates(page_html, source["bank"], source["url"]))
        except Exception:  # noqa: BLE001 - one unavailable PBI page must not break the landing
            failed += 1
    changes.sort(key=lambda item: (item["dateSort"], -item["order"]), reverse=True)
    return changes, failed


def parse_pbi_updates(page_html: str, bank: str, source_page: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    updates_anchor = soup.find(id="updates")
    if updates_anchor is None:
        return []
    container = _first_tag_sibling(updates_anchor)
    if container is None:
        return []

    records = []
    pending_text = ""
    order = 1
    for node in container.descendants:
        if not isinstance(node, Tag):
            continue
        if node.name == "p":
            text = _news_text(node)
            if text and "Последние изменения" not in text:
                pending_text = text
        elif node.name == "footer" and pending_text:
            date_label = _clean_text(node.get_text(" ", strip=True))
            records.append({
                "bank": bank,
                "dateLabel": date_label,
                "dateSort": _date_sort(date_label),
                "text": pending_text,
                "sourcePage": source_page,
                "order": order,
            })
            order += 1
            pending_text = ""
    return records


def group_by_bank(changes: list[dict]) -> list[dict]:
    by_bank = {}
    for change in changes:
        by_bank.setdefault(change["bank"], []).append(change)
    source_order = {source["bank"]: idx for idx, source in enumerate(PBI_UPDATE_SOURCES)}
    return [
        {"name": bank, "changes": bank_changes}
        for bank, bank_changes in sorted(
            by_bank.items(),
            key=lambda item: source_order.get(item[0], len(source_order)),
        )
    ]


def render_html(banks: list[dict], generated_at: datetime) -> str:
    app_html = render_changes_app(banks, generated_at)
    payload = _esc(json.dumps({"changes": banks}, ensure_ascii=False))
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Последние изменения премиальных программ</title>
  <style>{changes_css()}</style>
</head>
<body>
  <main class="page">
    {app_html}
  </main>
  <script id="data" type="application/json">{payload}</script>
  <script>{changes_js()}initChangesApp(document.querySelector('.changes-app'));</script>
</body>
</html>"""


def render_changes_panel(banks: list[dict], generated_at: datetime) -> str:
    changes_count = sum(len(bank["changes"]) for bank in banks)
    return f"""
      <section class="changes-panel js-changes-panel" data-storage-key="sber_vs_changes_collapsed">
        <div class="changes-panel-summary">
          <button type="button" class="changes-panel-toggle js-changes-show"
              data-open-label="Последние изменения · {changes_count} событий · Скрыть"
              data-closed-label="Последние изменения · {changes_count} событий · Показать"
              aria-expanded="false">
            Последние изменения · {changes_count} событий · Показать
          </button>
        </div>
        <div class="changes-panel-body js-changes-panel-body" hidden>
          {render_changes_app(banks, generated_at)}
          <div class="changes-sticky-close">
            <button type="button" class="changes-hide-btn compact js-changes-hide"
                aria-label="Скрыть раздел последних изменений">
              Скрыть изменения ↑
            </button>
          </div>
        </div>
      </section>"""


def render_changes_app(banks: list[dict], generated_at: datetime) -> str:
    bank_options = "\n".join(
        f'<option value="{_esc(bank["name"])}">{_esc(bank["name"])}</option>'
        for bank in banks
    )
    bank_sections = "\n".join(_render_bank(bank) for bank in banks)
    changes_count = sum(len(bank["changes"]) for bank in banks)
    return f"""
    <section class="changes-app">
    <header class="changes-top">
      <p class="eyebrow">PremiumBanking.info</p>
      <h1>Последние изменения</h1>
      <div class="changes-stats">
        <span><b>{len(banks)}</b> банков</span>
        <span><b>{changes_count}</b> публикаций</span>
      </div>
    </header>
    <section class="changes-filters" aria-label="Фильтры">
      <label>Банк
        <select class="js-change-bank-filter">
          <option value="">Все банки</option>
          {bank_options}
        </select>
      </label>
      <label>Период
        <select class="js-change-period-filter">
          <option value="">Все даты</option>
          <option value="30">30 дней</option>
          <option value="90">90 дней</option>
          <option value="365">Год</option>
        </select>
      </label>
    </section>
    <section class="changes-banks">
      {bank_sections or '<p class="empty">Публикации PremiumBanking.info не найдены.</p>'}
    </section>
    </section>"""


def _render_bank(bank: dict) -> str:
    changes_html = "\n".join(_render_change(change) for change in bank["changes"])
    return f"""
      <section class="change-bank js-change-bank" data-bank="{_esc(bank['name'])}">
        <h2>{_esc(bank['name'])}</h2>
        <div class="timeline">
          {changes_html}
        </div>
      </section>"""


def _render_change(change: dict) -> str:
    change_id = f"{change.get('bank', '')}-{change.get('order', '')}"
    source_url = _source_button_url(change)
    return f"""
          <article class="change js-change-card"
              data-change-id="{_esc(change_id)}"
              data-date="{_esc(change.get('dateSort', ''))}">
            <div class="change-head">
              <span>{_esc(change.get('dateLabel', ''))}</span>
            </div>
            <p>{_esc(change.get('text', ''))}</p>
            <a href="{_esc(source_url)}" target="_blank" rel="noreferrer">Источник</a>
          </article>"""


def _fetch_pbi_page(url: str) -> str:
    if not _robots_allows(url):
        raise RuntimeError(f"robots.txt disallows {url}")
    response = requests.get(url, timeout=25, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def _source_button_url(change: dict) -> str:
    bank = change.get("bank", "")
    return _clean_url(SOURCE_BUTTON_URLS.get(bank) or change.get("sourcePage", ""))


def _robots_allows(url: str) -> bool:
    parser = robotparser.RobotFileParser()
    parser.set_url("https://premiumbanking.info/robots.txt")
    parser.read()
    return parser.can_fetch(USER_AGENT, url)


def _first_tag_sibling(node) -> Optional[Tag]:
    sibling = node.next_sibling
    while sibling is not None:
        if isinstance(sibling, Tag):
            return sibling
        sibling = sibling.next_sibling
    return None


def _news_text(node: Tag) -> str:
    for link in node.find_all("a"):
        if _clean_text(link.get_text(" ", strip=True)).lower() == "подробнее":
            link.decompose()
    text = _clean_text(node.get_text(" ", strip=True))
    text = re.sub(r"\s+\.", ".", text)
    return re.sub(r"\.{2,}", ".", text)


def _date_sort(date_label: str) -> str:
    text = _clean_text(date_label).replace("\u00a0", " ").lower()
    year_match = re.search(r"(20\d{2})", text)
    year = year_match.group(1) if year_match else "1900"
    month = "01"
    for token, number in MONTHS.items():
        if re.search(rf"\b{re.escape(token)}\b", text):
            month = number
            break
    return f"{year}-{month}-01"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("&nbsp", " ")).strip()


def _clean_url(value) -> str:
    return re.sub(r"\s*:\s*//\s*", "://", _clean(value))


def _clean(value) -> str:
    return "" if value is None else str(value).strip()


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def changes_js() -> str:
    return _JS


def changes_css(embedded: bool = False) -> str:
    return _EMBED_CSS if embedded else _CSS


_JS = """
function changeFilters(root) {
  return {
    bank: root.querySelector('.js-change-bank-filter'),
    period: root.querySelector('.js-change-period-filter')
  };
}

function withinChangePeriod(dateText, days) {
  if (!days || !dateText) return true;
  const date = new Date(dateText + 'T00:00:00');
  if (Number.isNaN(date.getTime())) return true;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - Number(days));
  return date >= cutoff;
}

function applyChangeFilters(root) {
  const filters = changeFilters(root);
  const bankValue = filters.bank.value;
  const periodValue = filters.period.value;
  root.querySelectorAll('.js-change-bank').forEach(bank => {
    const bankMatch = !bankValue || bank.dataset.bank === bankValue;
    let visibleCount = 0;
    bank.querySelectorAll('.js-change-card').forEach(change => {
      const visible = bankMatch && withinChangePeriod(change.dataset.date, periodValue);
      change.hidden = !visible;
      if (visible) visibleCount += 1;
    });
    bank.hidden = visibleCount === 0;
  });
}

function initChangesApp(root) {
  if (!root) return;
  Object.values(changeFilters(root)).forEach(filter => {
    if (filter) filter.addEventListener('change', () => applyChangeFilters(root));
  });
  applyChangeFilters(root);
}

function initChangesPanel(panel) {
  if (!panel) return;
  const key = panel.dataset.storageKey || 'changes_collapsed';
  const showButton = panel.querySelector('.js-changes-show');
  const body = panel.querySelector('.js-changes-panel-body');
  const hideButtons = panel.querySelectorAll('.js-changes-hide');
  const stored = getChangesPanelStorage(key);
  const collapsed = stored === null ? true : stored !== 'false';

  function setCollapsed(nextCollapsed, options = {}) {
    body.hidden = nextCollapsed;
    showButton.setAttribute('aria-expanded', String(!nextCollapsed));
    showButton.textContent = nextCollapsed
      ? showButton.dataset.closedLabel
      : showButton.dataset.openLabel;
    panel.classList.toggle('is-open', !nextCollapsed);
    setChangesPanelStorage(key, String(nextCollapsed));
    if (nextCollapsed && options.scroll) {
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      window.setTimeout(() => showButton.focus({ preventScroll: true }), 260);
    }
    if (!nextCollapsed) {
      initChangesApp(panel.querySelector('.changes-app'));
    }
  }

  showButton.addEventListener('click', () => setCollapsed(!body.hidden));
  hideButtons.forEach((button) => {
    button.addEventListener('click', () => setCollapsed(true, { scroll: true }));
  });
  setCollapsed(collapsed);
}

function getChangesPanelStorage(key) {
  try {
    return window.localStorage ? window.localStorage.getItem(key) : null;
  } catch (_error) {
    return null;
  }
}

function setChangesPanelStorage(key, value) {
  try {
    if (window.localStorage) window.localStorage.setItem(key, value);
  } catch (_error) {
    // Storage can be unavailable in some embedded file viewers.
  }
}
"""


_BASE_CSS = """
:root {
  color-scheme: light;
  --text: #17202a;
  --muted: #667085;
  --line: #d8dee8;
  --panel: #ffffff;
  --bg: #f5f7fb;
  --accent: #0f766e;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.page { max-width: 1180px; margin: 0 auto; padding: 28px 18px 48px; }
"""


_EMBED_CSS = """
.changes-app {
  --text: #17202a;
  --muted: #667085;
  --line: #d8dee8;
  --panel: #ffffff;
  --bg: #f5f7fb;
  --accent: var(--green, #0f766e);
  color: var(--text);
}
.changes-top { margin-bottom: 22px; }
.eyebrow { margin: 0 0 6px; color: var(--accent); font-weight: 700; }
.changes-app h1 { margin: 0; font-size: clamp(30px, 5vw, 54px); line-height: 1.05; letter-spacing: 0; }
.updated { margin: 12px 0 0; color: var(--muted); }
.changes-stats { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 16px; }
.changes-stats span {
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 8px;
  padding: 9px 12px;
}
.changes-filters {
  display: grid;
  grid-template-columns: repeat(2, minmax(180px, 1fr));
  gap: 12px;
  margin: 22px 0;
}
.changes-app label { display: grid; gap: 6px; color: var(--muted); font-size: 13px; }
.changes-app select {
  min-height: 40px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  color: var(--text);
  padding: 0 10px;
  font: inherit;
}
.changes-banks { display: grid; gap: 18px; }
.change-bank { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; }
.changes-app h2 { margin: 0 0 14px; font-size: 24px; letter-spacing: 0; }
.timeline { display: grid; gap: 12px; }
.change {
  border-left: 3px solid var(--accent);
  padding: 12px 0 12px 14px;
}
.change-head { display: flex; gap: 8px; flex-wrap: wrap; color: var(--muted); font-size: 13px; }
.change p { margin: 6px 0 10px; }
.changes-app a { color: var(--accent); font-weight: 700; }
.empty { color: var(--muted); background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }
.changes-panel { margin-top: 18px; border: 1px solid #cfe5da; border-radius: 8px; background: var(--panel); }
.changes-panel-summary { padding: 0; }
.changes-panel-toggle {
  width: 100%;
  min-height: 48px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: #eef8f2;
  color: var(--text);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  font: inherit;
  font-weight: 700;
  text-align: left;
}
.changes-panel-toggle:hover,
.changes-panel-toggle:focus-visible {
  background: #e2f3ea;
  border-color: #9ecfb6;
  outline: 2px solid color-mix(in srgb, var(--accent) 35%, transparent);
  outline-offset: -2px;
  color: var(--accent);
}
.changes-panel-body { padding: 0 14px 16px; }
.changes-hide-btn {
  min-height: 44px;
  border: 1px solid #9ecfb6;
  border-radius: 8px;
  background: #e7f6ed;
  color: #0b6b3f;
  cursor: pointer;
  padding: 9px 12px;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
}
.changes-hide-btn:hover,
.changes-hide-btn:focus-visible {
  background: #d8efdf;
  border-color: #4da375;
  outline: 2px solid color-mix(in srgb, var(--accent) 28%, transparent);
  outline-offset: 2px;
}
.changes-sticky-close {
  position: sticky;
  bottom: 12px;
  z-index: 4;
  display: flex;
  justify-content: flex-end;
  pointer-events: none;
  margin-top: 14px;
  padding-right: 10px;
}
.changes-sticky-close .changes-hide-btn {
  pointer-events: auto;
  box-shadow: 0 8px 22px rgba(23, 32, 42, 0.16);
}
.changes-panel:not(.is-open) .changes-sticky-close { display: none; }
.changes-panel .changes-app { padding-top: 16px; }
.changes-panel .changes-app h1 { font-size: clamp(24px, 4vw, 36px); }
@media (max-width: 760px) {
  .changes-filters { grid-template-columns: 1fr; }
  .changes-panel-body { padding-inline: 10px; }
  .changes-hide-btn { width: 100%; }
  .changes-sticky-close { bottom: 8px; }
  .changes-sticky-close .changes-hide-btn { width: auto; max-width: calc(100vw - 48px); }
}
"""


_CSS = _BASE_CSS + _EMBED_CSS
