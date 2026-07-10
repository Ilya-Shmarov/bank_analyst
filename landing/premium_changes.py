# -*- coding: utf-8 -*-
"""Static landing with premium program changes from premiumbanking.info."""

import html
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from scanner.fetch import Fetcher
from scanner.parse import normalize_text


BANK_PAGES = [
    {"id": "sber", "name": "Сбер", "url": "https://premiumbanking.info/sber"},
    {
        "id": "alfabank",
        "name": "Альфа-Банк",
        "url": "https://premiumbanking.info/alfabank",
    },
    {"id": "vtb", "name": "ВТБ", "url": "https://premiumbanking.info/vtb"},
    {
        "id": "gazprombank",
        "name": "Газпромбанк",
        "url": "https://premiumbanking.info/gazprombank",
    },
    {"id": "ozon", "name": "Озон Банк", "url": "https://premiumbanking.info/ozon"},
    {
        "id": "raiffeisen",
        "name": "Райффайзен",
        "url": "https://premiumbanking.info/raiffeisen",
    },
    {"id": "tbank", "name": "Т-Банк", "url": "https://premiumbanking.info/tbank"},
]

MAX_CHANGES_PER_BANK = 6
DATE_RE = re.compile(
    r"^(?:янв|фев|март|мар|апр|май|июнь|июн|июль|июл|авг|сент|сен|окт|ноя|дек)"
    r"\.?\s+\d{4}$",
    flags=re.IGNORECASE,
)


def build_premium_changes_landing(raw_dir: Path, output_path: Path) -> dict:
    """Fetch source pages, extract change blocks, and write a static HTML page."""
    fetched_at = datetime.now()
    fetcher = Fetcher(raw_dir)
    banks = []

    for bank in BANK_PAGES:
        result = fetcher.fetch([bank["url"]], f"premium_changes_{bank['id']}",
                               fetched_at.strftime("%Y-%m-%d"))
        if result.status != "ok":
            banks.append({
                **bank,
                "status": "error",
                "error": result.error or result.status,
                "changes": [],
            })
            continue
        banks.append({
            **bank,
            "status": "ok",
            "error": "",
            "changes": extract_changes(result.html),
        })

    html_text = render_html(banks, fetched_at)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")

    changes_count = sum(len(bank["changes"]) for bank in banks)
    failed_count = sum(1 for bank in banks if bank["status"] != "ok")
    return {
        "output": str(output_path),
        "banks": len(banks),
        "changes": changes_count,
        "failed": failed_count,
    }


def extract_changes(source_html: str) -> list[dict]:
    """Extract dated change entries from the source page text."""
    lines = _page_lines(source_html)
    start = _find_changes_start(lines)
    if start is None:
        return []

    entries = []
    pending_text = []
    pending_date = "актуальное изменение"
    for line in lines[start:]:
        if _is_section_end(line):
            break
        if _is_noise(line):
            continue
        if DATE_RE.match(line):
            if pending_text:
                entries.append(_change_entry(pending_date, pending_text))
                pending_text = []
            pending_date = line
            continue
        cleaned = _clean_change_text(line)
        if cleaned:
            pending_text.append(cleaned)
    if pending_text:
        entries.append(_change_entry(pending_date, pending_text))
    return entries[:MAX_CHANGES_PER_BANK]


def render_html(banks: list[dict], fetched_at: datetime) -> str:
    """Render the standalone HTML document."""
    changes_count = sum(len(bank["changes"]) for bank in banks)
    bank_cards = "\n".join(_render_bank(bank) for bank in banks)
    generated = fetched_at.strftime("%d.%m.%Y %H:%M")
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Изменения премиальных программ</title>
  <style>{_CSS}</style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="eyebrow">Премиальный банкинг РФ</p>
      <h1>Изменения премиальных программ</h1>
      <p class="lead">Последние обновления по Сберу, Альфа-Банку, ВТБ,
      Газпромбанку, Озон Банку, Райффайзену и Т-Банку.</p>
      <div class="stats">
        <div><b>{len(banks)}</b><span>банков</span></div>
        <div><b>{changes_count}</b><span>изменений</span></div>
        <div><b>{_esc(generated)}</b><span>дата сборки</span></div>
      </div>
    </section>
    <section class="grid">
      {bank_cards}
    </section>
  </main>
</body>
</html>"""


def _page_lines(source_html: str) -> list[str]:
    soup = BeautifulSoup(source_html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [normalize_text(line) for line in text.splitlines()]
    return [line for line in lines if line]


def _find_changes_start(lines: list[str]):
    for idx, line in enumerate(lines):
        low = line.lower()
        if ("последние изменения" in low
                and "премиальн" in low
                and "программ" in low):
            return idx + 1
    return None


def _is_section_end(line: str) -> bool:
    low = line.lower()
    return (
        low.startswith("список всех премиальных уровней")
        or low.startswith("premiumbanking.info")
        or low.startswith("рассылка")
        or low.startswith("письма для премиалов")
        or low.startswith("формат рассылки")
        or low.startswith("© ")
        or low == "сравнить уровни"
    )


def _is_noise(line: str) -> bool:
    low = line.lower()
    return (
        low in {"new", "новое", "подробнее", "."}
        or low.startswith("выбрать уровень")
        or low.startswith("сравнить премиум")
        or low.startswith("задать вопрос")
    )


def _clean_change_text(line: str) -> str:
    text = re.sub(r"\bПодробнее\b", "", line, flags=re.IGNORECASE)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text or _is_noise(text) or DATE_RE.match(text):
        return ""
    return text + "."


def _change_entry(date: str, text_parts: list[str]) -> dict:
    text = " ".join(text_parts)
    text = re.sub(r"\s+", " ", text).strip()
    return {
        "date": date,
        "text": text,
        "category": _category(text),
    }


def _category(text: str) -> str:
    low = text.lower()
    if any(word in low for word in (
        "остат", "трат", "зарплат", "стоимость", "обслужив",
        "платн", "комисс", "услов",
    )):
        return "Условия"
    if any(word in low for word in (
        "бизнес-зал", "бз", "ресторан", "такси", "дмс", "страх",
        "консьерж", "медицин", "фаст", "трансфер", "fitmost",
        "фитмост", "persona", "on·pass", "·on·pass",
    )):
        return "Привилегии"
    if any(word in low for word in (
        "старт", "новые уровни", "перезапуск", "название", "переимен",
        "программа", "присоединился",
    )):
        return "Программа"
    return "Изменение"


def _render_bank(bank: dict) -> str:
    if bank["status"] != "ok":
        changes_html = (
            f'<p class="empty">Данные не получены: {_esc(bank["error"])}</p>'
        )
    elif not bank["changes"]:
        changes_html = '<p class="empty">Раздел изменений не найден</p>'
    else:
        changes_html = "\n".join(_render_change(change) for change in bank["changes"])

    return f"""
      <article class="bank-card">
        <div class="bank-head">
          <h2><a href="{_esc(bank['url'])}" target="_blank" rel="noreferrer">{_esc(bank['name'])}</a></h2>
          <span>{len(bank['changes'])} изменений</span>
        </div>
        <div class="timeline">
          {changes_html}
        </div>
      </article>"""


def _render_change(change: dict) -> str:
    return f"""
          <div class="change">
            <div class="change-meta">
              <span class="date">{_esc(change['date'])}</span>
              <span class="tag">{_esc(change['category'])}</span>
            </div>
            <p>{_esc(change['text'])}</p>
          </div>"""


def _esc(value) -> str:
    return html.escape(str(value or ""))


_CSS = """
:root {
  --bg: #f7f8f6;
  --card: #ffffff;
  --ink: #17231d;
  --muted: #64746b;
  --line: #dfe7e1;
  --green: #188f4f;
  --green-soft: #e5f4eb;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  -webkit-tap-highlight-color: rgba(24, 143, 79, 0.18);
}
a { touch-action: manipulation; }
.page { max-width: 1160px; margin: 0 auto; padding: 36px 18px 56px; }
.hero { padding: 18px 0 28px; border-bottom: 1px solid var(--line); }
.eyebrow {
  margin: 0 0 8px;
  color: var(--green);
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
}
h1 { margin: 0; font-size: 42px; line-height: 1.08; letter-spacing: 0; }
.lead { max-width: 780px; margin: 14px 0 0; color: var(--muted); font-size: 17px; }
.stats { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }
.stats div {
  min-width: 150px;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px 14px;
}
.stats b { display: block; font-size: 24px; color: var(--green); }
.stats span { color: var(--muted); font-size: 13px; }
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 26px;
}
.bank-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 8px;
  min-width: 0;
  padding: 18px;
}
.bank-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
h2 { margin: 0; font-size: 22px; letter-spacing: 0; }
h2 a { color: var(--ink); display: inline-flex; align-items: center;
  min-height: 44px; text-decoration: none; }
h2 a:hover { color: var(--green); }
.bank-head span { color: var(--muted); font-size: 13px; white-space: nowrap; }
.timeline { display: grid; gap: 12px; }
.change {
  border-left: 3px solid var(--green);
  padding: 2px 0 2px 12px;
}
.change-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 4px;
}
.date { color: var(--muted); font-size: 13px; font-weight: 700; }
.tag {
  background: var(--green-soft);
  color: var(--green);
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 700;
}
.change p { margin: 0; }
.empty { color: var(--muted); margin: 0; }
@media (max-width: 820px) {
  .page { padding: 24px 14px 42px; }
  h1 { font-size: 32px; }
  .stats div { flex: 1 1 138px; min-width: 0; }
  .grid { grid-template-columns: 1fr; }
  .bank-card { padding: 16px; }
  .bank-head { display: block; }
  .bank-head span { display: block; margin-top: 4px; }
}
"""
