# -*- coding: utf-8 -*-
"""
Дайджест изменений конкурентов — одностраничный HTML-лендинг.

Переиспользует changelog из data/history.json (отдельный скан не нужен):
берёт изменения за последние DIGEST_WINDOW_DAYS дней, классифицирует по
категориям из digest/rules.json (правила расширяются без правки кода)
и рендерит статический output/digest.html — открывается двойным кликом.

Опционально (--use-ai-summary): человекочитаемая формулировка каждой
новости через Anthropic API (нужен ANTHROPIC_API_KEY и пакет `anthropic`).
Без флага используется шаблонная формулировка — API не обязателен.
"""

import html
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("digest")

DIGEST_WINDOW_DAYS = 60
RULES_PATH = Path(__file__).resolve().parent / "rules.json"
AI_MODEL = "claude-opus-4-8"


def load_rules() -> dict:
    with open(RULES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def classify(change: dict, rules: dict) -> str:
    """Возвращает id категории для записи changelog."""
    if change.get("bank") == "— система —":
        return "system"
    old = (change.get("old") or "").lower()
    new = (change.get("new") or "").lower()
    field = (change.get("field") or "").lower()

    for cat in rules["categories"]:
        if cat.get("_default"):
            continue
        if any(p in new for p in cat.get("patterns_new", [])):
            return cat["id"]
        if any(p in old for p in cat.get("patterns_old", [])):
            return cat["id"]
        if cat.get("patterns_field") and any(
                p in field for p in cat["patterns_field"]):
            return cat["id"]
    return next(c["id"] for c in rules["categories"] if c.get("_default"))


def humanize(change: dict) -> str:
    """Шаблонная человекочитаемая формулировка (без AI)."""
    field = change.get("field", "")
    old = change.get("old", "")
    new = change.get("new", "")
    if old == "не найдено" and new != "не найдено":
        return f"Появились данные по «{field}» — раньше информации не было."
    if new == "не найдено" and old != "не найдено":
        return f"Данные по «{field}» пропали из источников — проверить, не свернул ли банк условие."
    if "тир добавлен" in new:
        return "В отчёт добавлен новый тир."
    return f"Изменилось «{field}»."


def ai_humanize(changes: list) -> dict:
    """Опционально: короткие читаемые описания через Anthropic API.
    Возвращает {index: text}; при любой ошибке — пустой словарь (fallback
    на шаблонные формулировки, дайджест не падает)."""
    try:
        import anthropic
    except ImportError:
        log.warning("Пакет `anthropic` не установлен — AI-саммари пропущено "
                    "(pip install anthropic)")
        return {}

    items = [
        {"i": i, "bank": c["bank"], "tier": c["tier"], "field": c["field"],
         "old": c["old"][:300], "new": c["new"][:300]}
        for i, c in enumerate(changes)
    ]
    prompt = (
        "Ты аналитик премиального банкинга. Для каждого изменения ниже напиши "
        "1-2 коротких предложения по-русски: что изменилось и почему это важно "
        "для продакт-менеджера конкурента. Не выдумывай цифры — используй только "
        "данные из «old»/«new». Верни строго JSON-объект {\"<i>\": \"текст\", ...} "
        "без другого текста.\n\n" + json.dumps(items, ensure_ascii=False)
    )
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        )
        text = next(b.text for b in response.content if b.type == "text")
        start, end = text.find("{"), text.rfind("}")
        parsed = json.loads(text[start:end + 1])
        return {int(k): v for k, v in parsed.items()}
    except Exception as exc:  # noqa: BLE001 — AI-саммари не должно ронять дайджест
        log.warning("AI-саммари не удалось (%s) — использую шаблонные "
                    "формулировки", exc)
        return {}


def build_digest(history_path: Path, output_path: Path,
                 use_ai_summary: bool = False) -> dict:
    """Собирает дайджест. Возвращает статистику для консоли."""
    with open(history_path, encoding="utf-8") as fh:
        history = json.load(fh)
    rules = load_rules()

    cutoff = datetime.now() - timedelta(days=DIGEST_WINDOW_DAYS)
    recent = []
    for change in history.get("changelog", []):
        try:
            dt = datetime.fromisoformat(change["scan_date"])
        except (ValueError, KeyError):
            continue
        if dt >= cutoff:
            recent.append(change)
    # свежие сначала
    recent.sort(key=lambda c: c["scan_date"], reverse=True)

    # Дедупликация: если поле менялось несколько раз за период (например,
    # несколько сканов за день), в дайджест идёт только последнее состояние —
    # лендинг про «что нового», полная история остаётся в Excel/history.json
    seen_keys = set()
    deduped = []
    for change in recent:
        key = (change.get("bank"), change.get("tier"), change.get("field"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(change)
    recent = deduped

    summaries = ai_humanize(recent) if use_ai_summary else {}

    grouped = defaultdict(list)
    for i, change in enumerate(recent):
        cat = classify(change, rules)
        grouped[cat].append((i, change))

    period_from = cutoff.strftime("%d.%m.%Y")
    period_to = datetime.now().strftime("%d.%m.%Y")
    banks = sorted({c["bank"] for c in recent if c["bank"] != "— система —"})

    html_text = _render(rules, grouped, summaries, recent,
                        period_from, period_to, banks)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")

    return {"total": len(recent), "banks": len(banks),
            "by_category": {cat: len(items) for cat, items in grouped.items()},
            "ai_used": bool(summaries)}


# ---------- рендер ----------

_CSS = """
:root { --bg:#f6f7f9; --card:#ffffff; --ink:#1c2733; --muted:#6b7a8c;
        --accent:#1f4e79; --line:#e3e8ee; --old:#b34a3d; --new:#2e7d4f; }
* { box-sizing:border-box; margin:0; padding:0; }
body { font:15px/1.55 -apple-system,'Segoe UI',Roboto,sans-serif;
       background:var(--bg); color:var(--ink); padding:32px 16px; }
.wrap { max-width:960px; margin:0 auto; }
header { margin-bottom:28px; }
h1 { font-size:26px; color:var(--accent); margin-bottom:6px; }
.meta { color:var(--muted); font-size:14px; }
.stats { display:flex; gap:12px; flex-wrap:wrap; margin-top:14px; }
.stat { background:var(--card); border:1px solid var(--line); border-radius:10px;
        padding:10px 16px; font-size:14px; }
.stat b { color:var(--accent); font-size:18px; display:block; }
section { margin-top:30px; }
h2 { font-size:19px; margin-bottom:12px; border-bottom:2px solid var(--line);
     padding-bottom:6px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px;
        padding:16px 18px; margin-bottom:12px; }
.card .head { display:flex; justify-content:space-between; flex-wrap:wrap;
              gap:6px; margin-bottom:6px; }
.card .who { font-weight:600; }
.card .who span { color:var(--muted); font-weight:400; }
.card .date { color:var(--muted); font-size:13px; white-space:nowrap; }
.card .summary { margin:6px 0 10px; }
.diff { font-size:13.5px; border-left:3px solid var(--line); padding-left:12px; }
.diff .old { color:var(--old); }
.diff .new { color:var(--new); }
.diff b { font-weight:600; }
.src { margin-top:8px; font-size:13px; }
.src a { color:var(--accent); text-decoration:none; }
.empty { color:var(--muted); font-style:italic; }
footer { margin-top:36px; color:var(--muted); font-size:13px; }
details.sys summary { cursor:pointer; color:var(--muted); font-size:14px;
                      margin-bottom:10px; }
"""


def _esc(text: str) -> str:
    return html.escape(str(text or ""))


def _card(change: dict, summary: str) -> str:
    src = change.get("source", "")
    url = change.get("source_url", "")
    src_html = ""
    if url:
        src_html = f'<div class="src">Источник: <a href="{_esc(url)}" target="_blank">{_esc(src or url)}</a></div>'
    elif src:
        src_html = f'<div class="src">Источник: {_esc(src)}</div>'
    return f"""
<div class="card">
  <div class="head">
    <div class="who">{_esc(change['bank'])} <span>→ {_esc(change['tier'])}</span></div>
    <div class="date">обнаружено {_esc(change['scan_date'][:16].replace('T', ' '))}</div>
  </div>
  <div class="summary">{_esc(summary)}</div>
  <div class="diff">
    <div><b>Поле:</b> {_esc(change['field'])}</div>
    <div class="old"><b>Было:</b> {_esc(change['old'][:400])}</div>
    <div class="new"><b>Стало:</b> {_esc(change['new'][:400])}</div>
  </div>
  {src_html}
</div>"""


def _render(rules, grouped, summaries, recent, period_from, period_to, banks):
    parts = [f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Дайджест изменений премиум-банкинга</title>
<style>{_CSS}</style></head><body><div class="wrap">
<header>
  <h1>Дайджест изменений: премиум-банкинг</h1>
  <div class="meta">Период: {period_from} — {period_to} (последние {DIGEST_WINDOW_DAYS} дней) ·
  сгенерировано {datetime.now().strftime('%d.%m.%Y %H:%M')}</div>
  <div class="stats">
    <div class="stat"><b>{len(recent)}</b>изменений</div>
    <div class="stat"><b>{len(banks)}</b>банков/подписок</div>
  </div>
</header>"""]

    for cat in rules["categories"]:
        items = grouped.get(cat["id"], [])
        parts.append(f'<section><h2>{cat["emoji"]} {_esc(cat["title"])} '
                     f'({len(items)})</h2>')
        if not items:
            parts.append('<div class="empty">Изменений в этой категории нет</div>')
        for i, change in items:
            summary = summaries.get(i) or humanize(change)
            parts.append(_card(change, summary))
        parts.append('</section>')

    sys_items = grouped.get("system", [])
    if sys_items:
        sys_cat = rules["system_category"]
        parts.append(f'<section><details class="sys"><summary>'
                     f'{sys_cat["emoji"]} {_esc(sys_cat["title"])} '
                     f'({len(sys_items)}) — развернуть</summary>')
        for i, change in sys_items:
            parts.append(_card(change, humanize(change)))
        parts.append('</details></section>')

    parts.append("""<footer>Дайджест собран из changelog сканера
competitor-scanner (data/history.json). Полная база — output/competitor_analysis.xlsx.
Дайджест дополняет Excel-отчёт, не заменяет его.</footer>
</div></body></html>""")
    return "\n".join(parts)
