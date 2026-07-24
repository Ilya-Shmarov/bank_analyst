# -*- coding: utf-8 -*-
"""Static bank-vs-bank comparison landing generated from comparison JSON.

Интеракция: пользователь выбирает Банк 1 → уровень пакета этого банка,
затем Банк 2 → уровень пакета; сравнение появляется на том же экране без
прокрутки страницы. Внутри сравнения — своя скроллируемая область с
зафиксированной шапкой выбранных уровней.

Терминология UI — «уровень пакета». Внутренний ключ данных `tier` не
переименовывается: его читают JSON-экспорт, Excel-отчёт и этот модуль как
контракт данных.
"""

import html
import json
import re
from datetime import datetime
from pathlib import Path

from landing import premium_changes
from scanner.formatting import (
    assert_user_visible_text,
    make_complete_summary,
    normalize_source_text,
    split_summary_and_details,
)
from scanner.scoring import SCORERS
from scanner.sources import NOT_FOUND, NOT_FOUND_AVAILABLE

INTL_SEGMENT = "digital-first (межд.)"

# Официальные курсы Банка России на дату текущего набора данных.
# Источник: https://www.cbr.ru/currency_base/daily/
# Значения нужны только для сопоставления страховых сумм в USD и EUR;
# исходная валюта и сумма продолжают отображаться без изменений.
INSURANCE_FX_RUB_PER_UNIT = {
    "$": 78.4049,
    "€": 89.4443,
}
INSURANCE_FX_DATE = "2026-07-24"
INSURANCE_FX_SOURCE_URL = (
    "https://www.cbr.ru/currency_base/daily/"
    "?UniDbQuery.Posted=True&UniDbQuery.To=24.07.2026"
)

FIELD_COLUMNS = {
    "entry_conditions": "Условия входа / поддержания уровня",
    "service_cost": "Стоимость обслуживания",
    "lounge_access": "Бизнес-залы (визиты, спутники)",
    "cashback": "Кэшбэк (ставка, категории, механика)",
    "transfers_payments": "Переводы и платежи без комиссии",
    "cash_withdrawal": "Снятие наличных",
    "supreme": "Supreme",
    "deposits": "Вклады / накопительные счета",
    "taxi": "Такси",
    "restaurants": "Рестораны",
    "insurance": "Страхование",
    "concierge": "Консьерж-сервис",
    "other_benefits": "Другие привилегии",
}

FIELD_LABELS = {
    "entry_conditions": "Условия входа",
    "service_cost": "Стоимость обслуживания",
    "lounge_access": "Бизнес-залы",
    "concierge": "Консьерж",
    "cashback": "Кэшбэк",
    "transfers_payments": "Переводы и платежи",
    "cash_withdrawal": "Снятие наличных",
    "supreme": "Supreme",
    "deposits": "Вклады и накопительные счета",
    "taxi": "Такси",
    "restaurants": "Рестораны",
    "insurance": "Страхование",
    "other_benefits": "Другие привилегии",
}

# Порядок атрибутов в таблице сравнения
COMPARE_FIELDS = (
    "entry_conditions",
    "service_cost",
    "lounge_access",
    "cashback",
    "transfers_payments",
    "cash_withdrawal",
    "supreme",
    "deposits",
    "taxi",
    "restaurants",
    "insurance",
    "concierge",
    "other_benefits",
)

# Служебное описание методики. Итоговый балл намеренно не рассчитывается:
# разные категории нельзя складывать без профиля и весов конкретного клиента.
def _methodology_text() -> str:
    return (
        "Условия сравниваются отдельно по каждой категории. Сначала применяется "
        "сравнение всех подтверждённых существенных параметров. Если полный "
        "порядок не получается, используется фиксированный приоритет показателей "
        "категории. Без цвета остаются только отсутствующие данные."
    )


def build_sber_vs_landing(data_path: Path, output_path: Path) -> dict:
    """Build the static bank comparison landing page."""
    rows = load_summary_rows(data_path)
    banks = build_payload(rows)
    changes = premium_changes.group_by_bank(premium_changes.load_changes(data_path))
    html_text = render_html(banks, rows, changes)
    html_text = "\n".join(line.rstrip() for line in html_text.splitlines()) + "\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")
    return {
        "output": str(output_path),
        "banks": len(banks),
        "levels": sum(len(b["levels"]) for b in banks),
    }


def load_summary_rows(data_path: Path) -> list[dict]:
    """Read normalized banking rows from the structured comparison JSON."""
    if not data_path.exists():
        raise FileNotFoundError(
            f"Comparison JSON not found: {data_path}. Run --scan-all first."
        )
    if data_path.suffix.lower() != ".json":
        raise ValueError(
            "Sber VS HTML must be generated from comparison JSON, not Excel."
        )

    payload = json.loads(data_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or "rows" not in payload:
        raise ValueError(f"Unsupported comparison JSON schema: {data_path}")
    rows = []
    for item in payload["rows"]:
        bank = _clean(item.get("bank"))
        tier = _clean(item.get("tier"))
        if not bank or not tier:
            continue
        field_records = item.get("fields", {})
        row = {
            "tier_id": _clean(item.get("tier_id")),
            "segment": _clean(item.get("segment")),
            "bank": bank,
            "tier": tier,
            "scan_date": _clean(item.get("scan_date")),
            "sources_ok": _clean(item.get("sources_ok")),
            "score": _score_total(item.get("score")),
            "divergent": "да" if any(
                bool(record.get("divergent"))
                for record in field_records.values()
                if isinstance(record, dict)
            ) else "нет",
        }
        row["fields"] = {
            key: _clean(_json_field_value(field_records.get(key)))
            for key in FIELD_COLUMNS
        }
        row["details"] = {
            key: _clean(_json_field_details(field_records.get(key)))
            for key in FIELD_COLUMNS
        }
        if row["segment"] and row["segment"] != INTL_SEGMENT:
            rows.append(row)
    return rows


def _json_field_value(record) -> str:
    if not isinstance(record, dict):
        return ""
    return record.get("display_value") or record.get("value") or ""


def _json_field_details(record) -> str:
    if not isinstance(record, dict):
        return ""
    return record.get("raw_text") or record.get("display_value") or record.get("value") or ""


def _score_total(score):
    if isinstance(score, dict):
        return _parse_float(score.get("total"))
    return _parse_float(score)


def build_payload(rows: list[dict]) -> list[dict]:
    """Group rows into banks → levels with pre-computed compare attributes."""
    by_bank = {}
    for row in rows:
        by_bank.setdefault(row["bank"], []).append(row)

    banks = []
    # Сбер первым (база сравнения), остальные по алфавиту
    order = sorted(by_bank, key=lambda name: (name != "Сбер", name.lower()))
    for name in order:
        levels = []
        for row in by_bank[name]:
            attrs = []
            for field in COMPARE_FIELDS:
                metric = _attr_metric(field, row)
                attr = {
                    "id": field,
                    "label": FIELD_LABELS[field],
                    "value": metric["value"],
                    "kind": metric.get("kind", "text"),
                    # Legacy scalar is retained for payload compatibility only.
                    # Browser ranking uses the structured evaluation below.
                    "score": metric["score"],
                    "evaluation": _category_evaluation(
                        field,
                        metric.get("evaluation_text") or row["fields"].get(field, ""),
                        metric.get("value"),
                        row,
                    ),
                    "note": metric["note"],
                    "details": metric.get("details", ""),
                }
                _validate_attr(attr, f"{row['bank']} / {row['tier']} / {field}")
                attrs.append(attr)
            levels.append({
                "tier": row["tier"],  # значение поля данных; в UI — уровень пакета
                "segment": row["segment"],
                "scan_date": (row.get("scan_date") or "")[:10],
                "entry_hint": _entry_hint(row, attrs),
                "entry_match": _entry_match(row),
                "attrs": attrs,
            })
        banks.append({"bank": name, "levels": levels})
    return banks


def _attr_metric(field: str, row: dict) -> dict:
    """Attribute display value + comparable score for one level."""
    field_record = row["fields"].get(field, "")
    raw = _json_field_value(field_record) if isinstance(field_record, dict) else field_record
    detail_raw = (
        _json_field_details(field_record)
        if isinstance(field_record, dict)
        else row.get("details", {}).get(field) or raw
    )
    if field == "entry_conditions":
        summary = _condition_summary(raw, row.get("tier_id"))
        return {"value": summary or "нет данных", "score": _entry_conditions_score(summary or raw),
                "note": _shorten(raw, 260), "details": _details(detail_raw, summary)}
    if field == "service_cost":
        cost_info = _service_cost_summary(row)
        cost = _monthly_rub_cost(raw)
        return {"value": cost_info["display"],
                "score": _service_cost_score(raw, cost_info["display"], cost),
                "note": _shorten(raw, 260), "details": _details(detail_raw, cost_info["display"])}
    if field == "other_benefits":
        override = _sber_landing_override(field, row)
        if override:
            return override
        benefits = _benefits_list(raw)
        return {"value": benefits, "score": None,
                "note": _shorten(raw, 260), "kind": "benefits", "details": ""}

    if _is_missing(raw):
        return {"value": NOT_FOUND_AVAILABLE, "score": None, "note": "", "details": ""}
    if raw.strip().startswith(("—", "-")):
        if field == "supreme":
            return {"value": "Не предусмотрено", "score": 0, "note": "", "details": ""}
        return {"value": "Не предусмотрено", "score": 0, "note": "", "details": "",
                "evaluation_text": raw}
    override = _sber_landing_override(field, row)
    if override:
        return override
    try:
        scorer_field = "taxi_restaurants" if field in ("taxi", "restaurants") else field
        metric, _legacy_score = SCORERS[scorer_field](raw)
    except Exception:  # noqa: BLE001 — шумный текст источника не роняет лендинг
        metric = "есть, детали не выделены" if _has_benefit(raw) else "нет"
    value = _benefit_display(field, raw, metric)
    if field in {"transfers_payments", "cash_withdrawal"} and not _rub_amounts(value):
        limit_evaluation = _limit_evaluation(raw, field)
        if limit_evaluation.get("status") == "comparable":
            summary = limit_evaluation.get("summary", "")
            if summary:
                value = f"{value.rstrip(' .')}. Лимит без комиссии: {summary}."
    score = _comparison_score(field, raw)
    public_raw = _insurance_display(raw) if field == "insurance" else raw
    public_details = (
        _insurance_display(detail_raw) if field == "insurance" else detail_raw
    )
    return {"value": value, "score": score, "note": _shorten(public_raw, 260),
            "details": _details(public_details, value)}


def _sber_landing_override(field: str, row: dict):
    """Narrow, source-backed presentation fixes for named landing levels."""
    bank = row.get("bank")
    tier_id = row.get("tier_id")
    if bank == "Альфа-Банк" and field == "restaurants" and tier_id == "alfa_aclub":
        value = (
            "Включено постоянно: безлимит по 2 500 ₽. Ограничения: один чек "
            "за одну дату до 5 000 ₽ списывает две компенсации по 2 500 ₽; "
            "только в аэропорту при вылете или прилёте, в дату поездки и один "
            "календарный день до или после неё; общий лимит с бизнес-залами."
        )
        return {
            "value": value,
            "score": _comparison_score(field, value),
            "note": value,
            "details": "",
            "evaluation_text": value,
        }
    if bank != "Сбер":
        return None
    text_by_field = {
        "lounge_access": {
            "sber_first_4": (
                "Включено постоянно: безлимит. Доступ через Mir Pass, "
                "ON·PASS, Частично и ON·PASS Premium."
            ),
            "sber_first_5": (
                "Включено постоянно: безлимит. Доступ через Mir Pass, "
                "ON·PASS, Частично и ON·PASS Premium."
            ),
            "sber_private_6": (
                "Включено постоянно: безлимит. Доступ через Mir Pass, "
                "ON·PASS, Частично и ON·PASS Premium."
            ),
        },
        "restaurants": {
            "sber_premier_2": "1 посещение в месяц на 2000 ₽ — опция «Такси и рестораны».",
            "sber_private_6": (
                "Включено постоянно: безлимит по 5000 ₽ — опция «Рестораны» "
                "2 чека в день"
            ),
        },
    }
    other_benefits_by_tier = {
        "sber_premier_2": (
            "• Здоровье — телемедицина, анализы, исследования [опция на выбор]\n"
            "• Самокат — 2 заказа по 1000 ₽ [опция на выбор]\n"
            "• Питомцы — лечение и консультации [опция на выбор]\n"
            "• Авто — помощь на дорогах, кэшбэк 15% за платные дороги и парковки [опция на выбор]\n"
            "• СберПрайм [включено постоянно]\n"
            "Условия выбора: одна опция в месяц (изменить можно до использования)"
        ),
        "sber_premier_3": (
            "• Здоровье — телемедицина, анализы, исследования [опция на выбор]\n"
            "• Спорт и красота — 6000 бонусных рублей Фитмост [опция на выбор]\n"
            "• Развлечения — до 5000 ₽ на Афиша.ру [опция на выбор]\n"
            "• Самокат — 2 заказа по 1500 ₽ [опция на выбор]\n"
            "• Питомцы — лечение и консультации [опция на выбор]\n"
            "• Авто — помощь на дорогах, кэшбэк 15% за платные дороги и парковки [опция на выбор]\n"
            "• СберПрайм [включено постоянно]\n"
            "• Обмен 10 бонусов = 7 ₽ с лимитом 12500 Б в мес\n"
            "Условия выбора: одна опция в месяц (изменить можно до использования)"
        ),
    }
    if field == "other_benefits" and tier_id in other_benefits_by_tier:
        raw = other_benefits_by_tier[tier_id]
        benefits = _benefits_list(raw)
        return {"value": benefits, "score": None,
                "note": "", "kind": "benefits", "details": "",
                "evaluation_text": raw}
    value = text_by_field.get(field, {}).get(tier_id)
    if not value:
        return None
    return {"value": value, "score": _comparison_score(field, value),
            "note": value, "details": "", "evaluation_text": value}


# ---------- рендер ----------

def render_html(banks: list[dict], rows: list[dict], changes: list[dict] = None) -> str:
    changes = changes or []
    scan_dates = sorted({r["scan_date"][:10] for r in rows if r.get("scan_date")})
    latest_scan = scan_dates[-1] if scan_dates else "нет данных"
    total_levels = sum(len(b["levels"]) for b in banks)
    payload = json.dumps(banks, ensure_ascii=False).replace("</", "<\\/")
    bank_chips = _render_bank_chips(banks)
    changes_panel = premium_changes.render_changes_panel(changes, datetime.now())

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Сравнение премиальных пакетов банков</title>
  <style>{_CSS}{premium_changes.changes_css(embedded=True)}</style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="eyebrow">Премиальный банкинг РФ</p>
      <h1>Сравнение уровней пакетов</h1>
      <p class="lead">Выберите Банк 1 и уровень пакета — мы предложим
      сопоставимые уровни других банков. После выбора трёх банков сравнение
      условий и привилегий появится на этой странице.</p>
      <div class="stats">
        <div><b>{len(banks)}</b><span>банков</span></div>
        <div><b>{total_levels}</b><span>уровней пакетов</span></div>
        <div><b>{_esc(latest_scan)}</b><span>дата данных</span></div>
      </div>
      {changes_panel}
    </section>

    <section class="pickers">
      <div class="picker" data-side="a">
        <h2>Банк 1</h2>
        <div class="chip-row banks">{bank_chips}</div>
        <h3 class="lvl-title" hidden>Уровень пакета</h3>
        <div class="chip-row levels"></div>
      </div>
      <div class="picker" data-side="b">
        <h2>Банк 2</h2>
        <div class="chip-row banks">{bank_chips}</div>
        <h3 class="lvl-title" hidden>Уровень пакета</h3>
        <div class="chip-row levels"></div>
      </div>
      <div class="picker" data-side="c">
        <h2>Банк 3</h2>
        <div class="chip-row banks">{bank_chips}</div>
        <h3 class="lvl-title" hidden>Уровень пакета</h3>
        <div class="chip-row levels"></div>
      </div>
    </section>
    <section id="recommendations" class="recommendations" hidden aria-live="polite">
      <div class="recommendations-head">
        <div>
          <p class="recommendations-kicker">Быстрый подбор</p>
          <h2>Подходящие уровни</h2>
        </div>
        <p id="recommendations-summary" class="recommendations-summary"></p>
      </div>
      <div id="recommendations-list" class="recommendation-grid"></div>
    </section>
    <p id="js-warning" class="js-warning">Если банки не выбираются, файл открыт
    во встроенном просмотрщике без JavaScript. Нажмите «Поделиться» → «Открыть
    в Safari» или откройте этот HTML в Chrome.</p>

    <section id="compare" hidden>
      <div class="compare-actions">
        <div>
          <p class="print-title">Сравнение премиальных пакетов</p>
          <p class="print-date">Дата данных: {_esc(latest_scan)}</p>
        </div>
        <button type="button" class="pdf-button" id="pdf-button">Выгрузить PDF</button>
      </div>
      <div class="cmp-scroll">
        <div class="cmp-head">
          <div class="cmp-attr-spacer" aria-hidden="true"></div>
          <div class="cmp-col" data-head="a"></div>
          <div class="cmp-col" data-head="b"></div>
          <div class="cmp-col" data-head="c"></div>
        </div>
        <table class="cmp-table">
          <thead>
            <tr><th>Атрибут</th><th data-th="a"></th><th data-th="b"></th><th data-th="c"></th></tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </section>
    <p id="hint" class="hint">Выберите банк и уровень пакета во всех трёх колонках —
    сравнение появится здесь.</p>

    <footer class="footer">
      <p>Данные — из JSON-экспорта сканера, у каждого значения зафиксирован
      источник, фрагмент исходного текста и дата проверки. Excel-отчёт —
      только представление этих данных. Дата данных:
      {_esc(latest_scan)}.</p>
    </footer>
  </main>
  <script id="data" type="application/json">{payload}</script>
  <script>{premium_changes.changes_js()}{_JS}</script>
</body>
</html>"""


# ---------- значения и форматирование ----------

def _render_bank_chips(banks: list[dict]) -> str:
    return "".join(
        f'<button type="button" class="chip" data-bank-index="{idx}">'
        f'{_esc(bank["bank"])}</button>'
        for idx, bank in enumerate(banks)
    )

def _service_cost_summary(row) -> dict:
    raw = row["fields"].get("service_cost", "")
    entry = row["fields"].get("entry_conditions", "")
    if row.get("tier_id") == "raif_premium_1":
        cost = _monthly_rub_cost(raw) or _monthly_rub_cost(entry)
        if cost is not None:
            return {"display": f"{_format_rub(cost)} ₽ в месяц"}
    combined_low = f"{raw} {entry}".lower()
    parts = []
    if "бесплат" in combined_low or re.search(r"\b0\s*(?:₽|руб)", combined_low,
                                              flags=re.IGNORECASE):
        parts.append("бесплатно при выполнении условий")
    cost = _monthly_rub_cost(raw)
    if cost is not None and cost > 0 and not parts and entry and not _is_missing(entry):
        parts.append("бесплатно при выполнении условий")
    if cost is not None and cost > 0:
        parts.append(f"{_format_rub(cost)} ₽ в месяц")
    if not parts and _is_missing(raw):
        parts.append("стоимость не указана")
    if not parts and raw:
        parts.append(_shorten(raw, 140))
    if not parts:
        parts.append("нет данных")
    parts[0] = parts[0][0].upper() + parts[0][1:]
    return {"display": " или ".join(parts)}


def _condition_summary(value: str, tier_id=None, limit: int = 5) -> str:
    text = _public_text(value)
    if not text or _is_missing(text):
        return ""
    keep_monthly_fee = tier_id in {"tbank_bronze", "raif_premium_1"}
    text = re.sub(r"\bзп\b", "зарплата", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*,\s*(?:и\s+)?или\s+", " | ", text,
                  flags=re.IGNORECASE)
    text = re.sub(r"\s+и\s+или\s+", " | ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*;\s*", " | ", text)
    text = re.sub(r"\s+\|\s+или\s+\|", " | ", text)
    text = re.sub(r"\|\s*или\s*\|", "|", text)
    text = re.sub(r"\s+", " ", text).strip(" |;")
    parts = []
    for part in re.split(r"\s*\|\s*", text):
        cleaned = part.strip(" ;")
        if not cleaned:
            continue
        if cleaned.lower().startswith("или ") and not keep_monthly_fee:
            cleaned = cleaned[4:].strip()
        low = cleaned.lower()
        if re.search(r"\d[\d\s]*\s*₽\s*в\s*мес", low) and not keep_monthly_fee:
            continue
        if "последний календарный день" in low:
            continue
        if "среднемесячный остаток" in low and parts:
            continue
        if cleaned and cleaned not in parts:
            parts.append(cleaned)
    if not parts:
        return normalize_source_text(text)
    shown = parts[:limit]
    summary = "; ".join(shown)
    if len(parts) > limit:
        summary += f"; ещё {len(parts) - limit}"
    if tier_id == "tbank_bronze" and len(parts) >= 2:
        fee = parts[0]
        shares = parts[1]
        if shares.lower().startswith("или "):
            shares = shares[4:].strip()
        return f"Уровень за {fee}\nили {shares}"
    if tier_id == "raif_premium_1":
        fee = next(
            (part for part in parts
             if re.search(r"\d[\d\s]*\s*₽\s*в\s*мес", part, flags=re.IGNORECASE)),
            "",
        )
        if fee:
            amount = re.search(r"(\d[\d\s]*)\s*₽", fee)
            if amount:
                return f"{_format_rub(amount.group(1).replace(' ', ''))} ₽ в месяц"
            return normalize_source_text(fee)
    return normalize_source_text(summary)


def _entry_hint(row: dict, attrs: list[dict]) -> str:
    entry_attr = next((attr for attr in attrs if attr["id"] == "entry_conditions"), None)
    summary = entry_attr["value"] if entry_attr else ""
    raw_record = row["fields"].get("entry_conditions", "")
    raw = _json_field_value(raw_record) if isinstance(raw_record, dict) else raw_record
    return _entry_hint_from_text(f"{summary} | {raw}")


def _entry_match(row: dict) -> dict:
    """Return a conservative capital interval for level recommendations."""
    raw_record = row["fields"].get("entry_conditions", "")
    raw = _json_field_value(raw_record) if isinstance(raw_record, dict) else raw_record
    return _entry_match_from_text(raw)


def _entry_match_from_text(value: str) -> dict:
    """Extract only standalone personal-capital entry routes from source text.

    The comparison evaluator intentionally merges alternative metrics.  A
    recommendation must be stricter: a lower balance combined with spending,
    salary, shares, joint access, or a monthly fee is not the same as a pure
    capital threshold and therefore cannot replace it.
    """
    empty = {
        "eligible": False,
        "min_amount": None,
        "max_amount": None,
        "label": "",
    }
    text = _public_text(value)
    if not text or _is_missing(text):
        return empty

    clauses = [
        part.strip(" ,;.|.")
        for part in re.split(
            r"\s*(?:[;|\n]+|,\s*(?=(?:и\s+)?или\b)|\bи\s+или\b|\bили\b|"
            r"\bи\b(?=\s*\d[^;|]*(?:моск|мск|регион)))\s*",
            text,
            flags=re.IGNORECASE,
        )
        if part.strip(" ,;.|.")
    ]
    excluded_markers = (
        "трат", "покуп", "оборот", "зарплат", "зп", "поступлен",
        "зачислен", "акци", "совмест", "платное обслуж", "в мес",
        "в месяц", "/мес",
    )
    generic = []
    regional = []
    for clause in clauses:
        low = clause.lower()
        amounts = _rub_amounts(clause)
        if len(amounts) != 1 or _monthly_rub_cost(clause) is not None:
            continue
        if any(marker in low for marker in excluded_markers):
            continue
        amount = amounts[0]
        if "моск" in low or re.search(r"\bмск\b", low):
            regional.append(("moscow", amount))
        elif "регион" in low:
            regional.append(("regions", amount))
        else:
            generic.append(amount)

    if generic:
        amount = generic[0]
        return {
            "eligible": True,
            "min_amount": amount,
            "max_amount": amount,
            "label": _compact_rub(amount),
        }
    if regional:
        values = [amount for _scope, amount in regional]
        minimum, maximum = min(values), max(values)
        return {
            "eligible": True,
            "min_amount": minimum,
            "max_amount": maximum,
            "label": f"{_rub_interval_label(minimum, maximum)} по региону",
        }
    return empty


def _rub_interval_label(minimum, maximum) -> str:
    left, right = _compact_rub(minimum), _compact_rub(maximum)
    if minimum == maximum:
        return left
    for suffix in (" млн ₽", " тыс ₽", " ₽"):
        if left.endswith(suffix) and right.endswith(suffix):
            return f"{left[:-len(suffix)]}–{right}"
    return f"{left}–{right}"


def _entry_hint_from_text(value: str) -> str:
    text = _public_text(value)
    if not text or _is_missing(text):
        return ""
    parts = [part.strip(" ;.") for part in re.split(r"\s*(?:\||;|\n)\s*", text) if part.strip(" ;.")]
    balance_keywords = (
        "баланс", "капитал", "остат", "счет", "счёт", "актив", "сбереж",
        "размещ", "совместном доступе", "сберпервый", "sber private",
    )
    spend_keywords = ("трат", "покуп", "оборот", "поступлен", "зачислен", "зарплат")

    def amounts(part: str) -> list[float]:
        return _rub_amounts(part)

    def is_monthly_fee(part: str) -> bool:
        low = part.lower()
        return bool(re.search(r"(?:в\s*мес|в\s*месяц|/мес)", low))

    candidates = []
    for part in parts:
        low = part.lower()
        if not amounts(part) or is_monthly_fee(part):
            continue
        if any(keyword in low for keyword in balance_keywords) and not any(
            keyword in low for keyword in spend_keywords
        ):
            candidates.append(part)
    if not candidates:
        candidates = [part for part in parts if amounts(part) and not is_monthly_fee(part)]
    if candidates:
        return f"от {_compact_rub(amounts(candidates[0])[0])}"

    monthly = _monthly_rub_cost(text)
    if monthly is not None:
        return f"{_compact_rub(monthly)} в месяц"
    return ""


def _clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_float(value):
    if value in ("", None):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _monthly_rub_cost(value: str):
    if not value:
        return None
    normalized = value.replace("\xa0", " ")
    match = re.search(
        r"(\d[\d\s.,]*)\s*(?:₽|руб)[^\n;]{0,20}(?:мес|месяц)",
        normalized,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    digits = re.sub(r"[^\d.,]", "", match.group(1)).replace(",", ".")
    try:
        return float(digits)
    except ValueError:
        return None


def _service_cost_score(raw: str, display: str, cost):
    if cost is not None:
        return -cost
    text = f"{raw} {display}".lower()
    if "бесплат" in text or re.search(r"\b0\s*(?:₽|руб)", text, flags=re.IGNORECASE):
        return 0
    return None


def _category_evaluation(field: str, raw_value, display_value, row: dict) -> dict:
    """Build a conservative, structured comparison contract for one cell."""
    if field == "other_benefits":
        return _benefits_evaluation(raw_value, display_value)

    comparison_value = (
        display_value
        if field == "service_cost" and isinstance(display_value, str)
        else raw_value
    )
    raw = _public_text(comparison_value)
    if _is_missing(raw):
        return _missing_evaluation()

    evaluators = {
        "entry_conditions": _entry_evaluation,
        "service_cost": _service_evaluation,
        "transfers_payments": lambda text: _limit_evaluation(
            text, "transfers_payments"
        ),
        "cash_withdrawal": lambda text: _limit_evaluation(
            text, "cash_withdrawal"
        ),
        "lounge_access": _lounge_evaluation,
        "taxi": lambda text: _compensation_evaluation(text, "taxi"),
        "restaurants": lambda text: _compensation_evaluation(text, "restaurants"),
        "cashback": _cashback_evaluation,
        "deposits": lambda text: _deposits_evaluation(
            text, (row.get("scan_date") or "")[:10]
        ),
        "insurance": _insurance_evaluation,
        "concierge": lambda text: _service_presence_evaluation(text, "concierge"),
        "supreme": lambda text: _service_presence_evaluation(text, "supreme"),
    }
    evaluator = evaluators.get(field)
    if evaluator is None:
        return _incomparable_evaluation("Для категории не задана надёжная метрика.")
    display_text = _public_text(display_value)
    if field in {
        "transfers_payments", "cash_withdrawal", "cashback", "deposits",
        "taxi", "restaurants", "insurance", "concierge", "supreme",
    } and display_text and not _is_missing(display_text):
        display_evaluation = evaluator(display_text)
        if display_evaluation.get("status") == "comparable":
            return display_evaluation
        raw_evaluation = evaluator(raw)
        if raw_evaluation.get("status") == "comparable":
            return raw_evaluation
        return display_evaluation
    return evaluator(raw)


def _evaluation(method: str, metrics: dict, directions: dict, summary: str,
                scope: dict = None, status: str = "comparable",
                reason: str = "") -> dict:
    return {
        "status": status,
        "method": method,
        "metrics": metrics,
        "directions": directions,
        "scope": scope or {},
        "summary": normalize_source_text(summary),
        "reason": normalize_source_text(reason),
    }


def _missing_evaluation(reason: str = "Нет подтверждённых данных для сравнения.") -> dict:
    return _evaluation("none", {}, {}, "Нет данных", status="missing", reason=reason)


def _incomparable_evaluation(reason: str, summary: str = "") -> dict:
    return _evaluation(
        "none", {}, {}, summary or "Условия требуют отдельного сравнения",
        status="incomparable", reason=reason,
    )


def _explicit_absence(text: str) -> bool:
    low = text.strip().lower()
    return (
        low.startswith(("—", "-", "нет —", "нет,"))
        or "не предусмотр" in low
        or "не заявлен" in low
        or "подтверждённо отсутств" in low
    )


def _availability_metric(text: str):
    low = text.lower()
    if "включено постоянно" in low or "всегда включ" in low:
        return 2
    if "опция на выбор" in low or re.search(r"\bопци[яи]\b", low):
        return 1
    return None


def _entry_evaluation(text: str) -> dict:
    if _explicit_absence(text):
        return _incomparable_evaluation(
            "Отсутствие требований к остатку нельзя приравнять к отсутствию доступа.",
            "Способ входа отличается",
        )

    fragments = [
        part.strip(" ,;.")
        for part in re.split(
            r"\s*(?:;|\n|,\s*(?=(?:или|и)\b)|\bили\b|\bи\b)\s*",
            text,
            flags=re.IGNORECASE,
        )
        if part.strip(" ,;.")
    ]
    metrics = {}
    labels = {}
    for fragment in fragments:
        amounts = _rub_amounts(fragment)
        if not amounts or _monthly_rub_cost(fragment) is not None:
            continue
        low = fragment.lower()
        if "акци" in low:
            key, label = "special_assets", "специальные активы"
        elif "совмест" in low:
            key, label = "joint_capital", "совместный капитал"
        elif any(marker in low for marker in ("трат", "покуп", "оборот")):
            key, label = "monthly_spend", "траты"
        elif any(marker in low for marker in ("зарплат", "зп", "зачислен", "поступлен")):
            key, label = "monthly_income", "зарплата/поступления"
        elif "моск" in low:
            key, label = "capital_moscow", "капитал для Москвы"
        elif "регион" in low:
            key, label = "capital_regions", "капитал для регионов"
        else:
            key, label = "capital", "капитал/остаток"
        amount = min(amounts)
        metrics[key] = min(metrics.get(key, amount), amount)
        labels[key] = label

    if not metrics:
        monthly = _monthly_rub_cost(text)
        if monthly is not None:
            return _incomparable_evaluation(
                "В условии найден только платный способ входа; он сравнивается в стоимости обслуживания.",
                f"Платный вход {_compact_rub(monthly)} в месяц",
            )
        return _incomparable_evaluation(
            "Не удалось надёжно выделить одинаковые способы входа.",
            _shorten(text, 110),
        )

    summary = "; ".join(
        f"{labels[key]} {_compact_rub(value)}" for key, value in metrics.items()
    )
    return _evaluation(
        "dominance", metrics, {key: "lower" for key in metrics}, summary,
        reason="Меньший порог лучше только для одинакового способа входа.",
    )


def _service_evaluation(text: str) -> dict:
    low = text.lower()
    cost = _monthly_rub_cost(text)
    conditional = bool(re.search(r"при\s+(?:выполн|услов|остат|трат)", low))
    free = "бесплат" in low or bool(
        re.search(r"\b0\s*(?:₽|руб)", low, flags=re.IGNORECASE)
    )
    if free and not conditional and (cost is None or cost == 0):
        rank, label = 4, "Безусловно бесплатно"
    elif free and conditional and cost is not None and cost > 0:
        rank = 3
        label = (
            "Два способа обслуживания: бесплатно при выполнении условий "
            f"или {_compact_rub(cost)} в месяц"
        )
    elif free and conditional:
        rank, label = 2, "Бесплатно при выполнении условий"
    elif cost is not None:
        rank, label = 1, f"{_compact_rub(cost)} в месяц"
    else:
        return _incomparable_evaluation(
            "Стоимость или условие бесплатности не выделены однозначно.",
            _shorten(text, 110),
        )
    metrics = {"service_rank": rank}
    directions = {"service_rank": "higher"}
    if cost is not None:
        metrics["monthly_cost"] = cost
        directions["monthly_cost"] = "lower"
    return _evaluation(
        "ordinal", metrics, directions, label,
        reason=(
            "Оценивается доступность обслуживания: безусловно бесплатный режим "
            "сильнее двух способов обслуживания, а бесплатность с платным "
            "запасным способом сильнее бесплатности только при выполнении условий."
        ),
    )


def _rub_amount_matches(text: str) -> list[dict]:
    pattern = re.compile(
        r"(?<![\d.,])(\d[\d\s.,]*)(?:\s*)(тыс|млн)?(?:\s*)(?:₽|руб)",
        flags=re.IGNORECASE,
    )
    matches = []
    for match in pattern.finditer(text):
        amount = _parse_rub_number(match.group(1))
        if amount is None:
            continue
        unit = (match.group(2) or "").lower()
        if unit == "тыс":
            amount *= 1000
        elif unit == "млн":
            amount *= 1_000_000
        matches.append({"amount": amount, "start": match.start(), "end": match.end()})
    return matches


def _limit_period(context: str):
    low = context.lower()
    if re.search(r"(?:в сутки|в день|/день|/сут|дневн)", low):
        return "day"
    if re.search(r"(?:в месяц|в мес|/мес|месячн)", low):
        return "month"
    if "расчётн" in low or "расчетн" in low:
        return "billing"
    if re.search(r"(?:за операци|на операци|за раз)", low):
        return "operation"
    if re.search(r"(?:в год|/год)", low):
        return "year"
    return None


def _limit_scope(text: str, field: str):
    low = text.lower()
    if field == "transfers_payments":
        if "расчётн" in low and "кредитн" in low:
            return "mixed_card_types"
        if "другого банка" in low and "по номеру карт" in low:
            return "card_to_other_bank"
        if "клиент" in low and "сбер" in low and "юрлиц" in low:
            return "sber_clients_and_legal_payments"
        if "сбп" in low:
            return "sbp"
        return "general_transfers"
    own = bool(re.search(r"банкоматах?\s+(?:втб|т-банка|банка)", low))
    other = "других банк" in low or "любых банкомат" in low or "по миру" in low
    if own and other:
        return "mixed_atm_scope"
    if other:
        return "all_atms"
    if own or "партнёр" in low or "партнер" in low:
        return "own_and_partner_atms"
    return "general_cash"


def _limit_evaluation(text: str, field: str) -> dict:
    low = text.lower()
    scope = _limit_scope(text, field)
    if scope in {"mixed_card_types", "mixed_atm_scope"}:
        return _incomparable_evaluation(
            "В одной ячейке указаны разные типы карт или области действия лимитов.",
            _shorten(text, 110),
        )
    if "при превышении" in low and any(
        marker in low for marker in ("без ограничений", "безлимит")
    ):
        return _incomparable_evaluation(
            "Лимит зависит от дополнительного условия и не является безусловным.",
            _shorten(text, 110),
        )
    if any(marker in low for marker in ("безлимит", "без ограничений", "не ограничен")):
        return _evaluation(
            "limit", {"unlimited": True, "limits": []}, {}, "Безлимит",
            scope={"operation_scope": scope},
            reason="Безлимит сравнивается только при одинаковой области действия.",
        )

    limits = []
    for match in _rub_amount_matches(text):
        after = text[match["end"]:min(len(text), match["end"] + 36)]
        before = text[max(0, match["start"] - 36):match["start"]]
        period = _limit_period(after) or _limit_period(before)
        if period:
            limits.append({"amount": match["amount"], "period": period})
    unique = []
    for item in limits:
        if item not in unique:
            unique.append(item)
    if not unique:
        return _incomparable_evaluation(
            "Не найден подтверждённый лимит с периодом действия.",
            _shorten(text, 110),
        )
    period_names = {
        "day": "в сутки", "month": "в месяц", "billing": "за расчётный период",
        "operation": "за операцию", "year": "в год",
    }
    summary = "; ".join(
        f"{_compact_rub(item['amount'])} {period_names[item['period']]}"
        for item in unique
    )
    return _evaluation(
        "limit", {"unlimited": False, "limits": unique}, {}, summary,
        scope={"operation_scope": scope},
        reason="Лимиты сравниваются без пересчёта суток в месяц.",
    )


def _lounge_evaluation(text: str) -> dict:
    if _explicit_absence(text):
        return _evaluation(
            "lounge", {"visits_monthly": 0}, {"visits_monthly": "higher"},
            "Бизнес-залы не предусмотрены",
        )
    low = text.lower()
    metrics = {}
    if any(marker in low for marker in ("безлимит", "без ограничений", "не ограничен")):
        metrics["unlimited"] = 1
    else:
        counts = _monthly_counts(text)
        if counts:
            metrics["visits_monthly"] = max(counts)
    annual_counts = _annual_counts(text)
    if annual_counts:
        metrics["annual_cap"] = max(annual_counts)
    availability = _availability_metric(text)
    if availability is not None:
        metrics["availability"] = availability
    guest = re.search(r"(\d+)\s*(?:гост|спутник)", low)
    if guest:
        metrics["guests"] = float(guest.group(1))
    if not metrics or set(metrics) == {"availability"}:
        return _incomparable_evaluation(
            "Количество посещений или безлимит не подтверждены.",
            _shorten(text, 110),
        )
    directions = {key: "higher" for key in metrics}
    if metrics.get("unlimited"):
        summary = "Безлимит"
    else:
        summary = f"{metrics.get('visits_monthly', 0):g} посещений в месяц"
    if availability == 2:
        summary += ", включено постоянно"
    elif availability == 1:
        summary += ", опция на выбор"
    return _evaluation(
        "lounge", metrics, directions, summary,
        reason="Учитываются посещения, постоянная включённость и подтверждённые гости.",
    )


def _compensation_evaluation(text: str, field: str) -> dict:
    if _explicit_absence(text):
        return _evaluation(
            "dominance", {"monthly_total": 0}, {"monthly_total": "higher"},
            "Не предусмотрено",
        )
    low = text.lower()
    if "только при" in low or "только для" in low:
        return _incomparable_evaluation(
            "Привилегия действует с отдельным ограничением.", _shorten(text, 110)
        )
    metrics = {}
    if any(marker in low for marker in ("безлимит", "без ограничений", "не ограничен")):
        metrics["unlimited"] = 1
    counts = _monthly_counts(text)
    if counts:
        metrics["monthly_count"] = max(counts)
    annual_counts = _annual_counts(text)
    if annual_counts:
        metrics["annual_count"] = max(annual_counts)
    amounts = _rub_amounts(text)
    per_use = re.search(
        r"(?:по|до|на|чек(?:а|ом)?\s*(?:до)?|поездк[аи]?\s*(?:до)?)\s*"
        r"(\d[\d\s.,]*)\s*(тыс|млн)?\s*₽",
        text,
        flags=re.IGNORECASE,
    )
    if per_use:
        parsed = _parse_rub_number(per_use.group(1))
        if parsed is not None:
            unit = (per_use.group(2) or "").lower()
            if unit == "тыс":
                parsed *= 1000
            elif unit == "млн":
                parsed *= 1_000_000
            metrics["per_use_limit"] = parsed
    if (
        "monthly_count" in metrics
        and "per_use_limit" not in metrics
        and len(amounts) == 1
        and not re.search(
            r"\d[\d\s.,]*\s*(?:тыс|млн)?\s*₽[^.;]{0,16}"
            r"(?:в\s*мес|в\s*месяц|/мес)",
            low,
        )
    ):
        metrics["per_use_limit"] = amounts[0]
    if amounts and not (metrics.get("unlimited") and "monthly_count" not in metrics):
        metrics["monthly_total"] = max(amounts)
    if "monthly_count" in metrics and "per_use_limit" in metrics:
        metrics["monthly_total"] = (
            metrics["monthly_count"] * metrics["per_use_limit"]
        )
    if "monthly_total" in metrics:
        if "annual_count" in metrics and "per_use_limit" in metrics:
            metrics["annual_total"] = (
                metrics["annual_count"] * metrics["per_use_limit"]
            )
        else:
            metrics["annual_total"] = metrics["monthly_total"] * 12
    availability = _availability_metric(text)
    if availability is not None:
        metrics["availability"] = availability
    if not metrics:
        return _incomparable_evaluation(
            "Количество и денежный лимит не выделены.", _shorten(text, 110)
        )
    labels = []
    if metrics.get("unlimited"):
        labels.append("безлимит")
    if "per_use_limit" in metrics:
        if re.search(r"посадочн(?:ый|ого|ому|ым|ом)\s+талон", low):
            labels.append(
                f"до {_compact_rub(metrics['per_use_limit'])} на один посадочный талон"
            )
        elif metrics.get("unlimited"):
            labels.append(f"до {_compact_rub(metrics['per_use_limit'])} за использование")
    if "monthly_total" in metrics:
        labels.append(f"до {_compact_rub(metrics['monthly_total'])} в месяц")
    if "annual_total" in metrics:
        labels.append(f"до {_compact_rub(metrics['annual_total'])} в год")
    if "monthly_count" in metrics:
        labels.append(f"{metrics['monthly_count']:g} использований")
    if "annual_count" in metrics:
        labels.append(f"до {metrics['annual_count']:g} в год")
    if availability == 1:
        labels.append("опция на выбор")
    elif availability == 2:
        labels.append("включено постоянно")
    return _evaluation(
        "dominance", metrics, {key: "higher" for key in metrics},
        ", ".join(labels) or FIELD_LABELS[field],
        reason="Сравниваются общий номинал, количество, лимит одного использования и статус подключения.",
    )


def _cashback_evaluation(text: str) -> dict:
    if _explicit_absence(text):
        return _evaluation(
            "dominance", {"rate": 0}, {"rate": "higher"}, "Кэшбэк не предусмотрен"
        )
    rates = [float(value.replace(",", ".")) for value in re.findall(
        r"(\d+(?:[.,]\d+)?)\s*%", text
    )]
    low = text.lower()
    metrics = {}
    base_match = re.search(r"базов[^\d]{0,24}(\d+(?:[.,]\d+)?)\s*%", low)
    if base_match:
        metrics["base_rate"] = float(base_match.group(1).replace(",", "."))
    if rates:
        metrics["max_rate"] = max(rates)
    if any(marker in low for marker in ("без лимита", "безлимит")):
        metrics["unlimited_accrual"] = 1
    category_match = re.search(r"(\d+)\s*катег", low)
    if category_match:
        metrics["categories"] = float(category_match.group(1))
    cap_match = re.search(
        r"(?:лимит[^\d]{0,24}|до\s*)"
        r"(\d[\d\s.,]*)\s*(тыс|млн)?\s*₽"
        r"(?:[^.;]{0,18}(?:в\s*мес|в\s*месяц|/мес))?",
        text,
        flags=re.IGNORECASE,
    )
    if cap_match:
        cap = _parse_rub_number(cap_match.group(1))
        if cap is not None:
            if (cap_match.group(2) or "").lower() == "тыс":
                cap *= 1000
            elif (cap_match.group(2) or "").lower() == "млн":
                cap *= 1_000_000
            metrics["monthly_cap"] = cap
    bonus_exchange = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(?:бонус\w*|б)\s*=\s*"
        r"(\d+(?:[.,]\d+)?)\s*₽",
        low,
    )
    if bonus_exchange:
        source_bonus = float(bonus_exchange.group(1).replace(",", "."))
        rub_value = float(bonus_exchange.group(2).replace(",", "."))
        if source_bonus > 0:
            metrics["bonus_rub_value"] = rub_value / source_bonus
    bonus_cap_match = re.search(
        r"лимит[^\d]{0,28}(\d[\d\s.,]*)\s*(?:б(?:/|\b)|бонус)",
        low,
    )
    if bonus_cap_match:
        bonus_cap = _parse_rub_number(bonus_cap_match.group(1))
        if bonus_cap is not None:
            metrics["monthly_bonus_cap"] = bonus_cap
            if "monthly_cap" not in metrics and "bonus_rub_value" in metrics:
                metrics["monthly_cap"] = bonus_cap * metrics["bonus_rub_value"]
    if not metrics:
        return _incomparable_evaluation(
            "Ставка, лимит и число категорий кэшбэка не указаны.",
            _shorten(text, 110),
        )
    summary = (
        f"до {metrics['max_rate']:g}%"
        if "max_rate" in metrics
        else "ставка не опубликована"
    )
    if "max_rate" in metrics and "base_rate" not in metrics:
        summary += ", оценка только по опубликованной максимальной ставке"
    return _evaluation(
        "dominance", metrics, {key: "higher" for key in metrics}, summary,
        reason="Максимальная ставка сравнивается отдельно от базовой ставки, категорий и лимита выплаты.",
    )


def _deposits_evaluation(text: str, scan_date: str) -> dict:
    if _explicit_absence(text):
        return _evaluation(
            "dominance", {"rate": 0}, {"rate": "higher"}, "Спецусловия не предусмотрены",
            scope={"scan_date": scan_date},
        )
    rates = [float(value.replace(",", ".")) for value in re.findall(
        r"(\d+(?:[.,]\d+)?)\s*%", text
    )]
    if not rates:
        return _incomparable_evaluation(
            "Ставка или надбавка не опубликована.", _shorten(text, 110)
        )
    rate = max(rates)
    metrics = {"rate": rate}
    directions = {"rate": "higher"}
    minimum = re.search(
        r"(?:от|min(?:imum)?)\s*(\d[\d\s.,]*)\s*(тыс|млн)?\s*₽", text,
        flags=re.IGNORECASE,
    )
    maximum = re.search(
        r"(?:до|max(?:imum)?)\s*(\d[\d\s.,]*)\s*(тыс|млн)?\s*₽", text,
        flags=re.IGNORECASE,
    )
    for match, key, direction in (
        (minimum, "minimum_amount", "lower"),
        (maximum, "maximum_amount", "higher"),
    ):
        if not match:
            continue
        amount = _parse_rub_number(match.group(1))
        if amount is None:
            continue
        if (match.group(2) or "").lower() == "тыс":
            amount *= 1000
        elif (match.group(2) or "").lower() == "млн":
            amount *= 1_000_000
        metrics[key] = amount
        directions[key] = direction
    return _evaluation(
        "dominance", metrics, directions,
        f"до {rate:g}%" if len(set(rates)) > 1 else f"{rate:g}%",
        scope={"scan_date": scan_date},
        reason=(
            "При нескольких опубликованных ставках сравнивается максимальная "
            "ставка категории; даты проверки должны совпадать."
        ),
    )


def _insurance_evaluation(text: str) -> dict:
    if _explicit_absence(text):
        return _evaluation(
            "dominance", {"coverage": 0}, {"coverage": "higher"},
            "Страхование не предусмотрено",
        )
    low = text.lower()
    availability = _availability_metric(text)
    coverage_match = re.search(
        r"([$€])\s*(\d+(?:[.,]\d+)?)"
        r"(?:\s*/\s*(\d+(?:[.,]\d+)?))?\s*(млн|тыс)?",
        text,
        flags=re.IGNORECASE,
    )
    metrics = {}
    scope = {}
    if coverage_match:
        first = float(coverage_match.group(2).replace(",", "."))
        second = coverage_match.group(3)
        second_value = float(second.replace(",", ".")) if second else first
        unit = (coverage_match.group(4) or "").lower()
        multiplier = 1_000_000 if unit == "млн" else 1000 if unit == "тыс" else 1
        currency = coverage_match.group(1)
        metrics["coverage"] = first * multiplier
        metrics["coverage_rub"] = (
            metrics["coverage"] * INSURANCE_FX_RUB_PER_UNIT[currency]
        )
        if second is not None:
            metrics["secondary_coverage"] = second_value * multiplier
            metrics["secondary_coverage_rub"] = (
                metrics["secondary_coverage"]
                * INSURANCE_FX_RUB_PER_UNIT[currency]
            )
        scope["currency"] = currency
    days = [float(value) for value in re.findall(r"(\d+)\s*(?:дн|дней|дня)", low)]
    if days:
        metrics["trip_days"] = max(days)
    if availability is not None:
        metrics["availability"] = availability
    if "по всему миру" in low or "worldwide" in low or "глобальн" in low:
        scope["territory"] = "worldwide"
    elif "росси" in low:
        scope["territory"] = "russia"
    if not metrics:
        return _incomparable_evaluation(
            "Страховая сумма и сопоставимый объём покрытия не выделены.",
            _shorten(text, 110),
        )
    summary_parts = []
    if "coverage" in metrics:
        summary_parts.append(
            f"владелец: {metrics['coverage']:g} {scope.get('currency', '')}".strip()
        )
    if "secondary_coverage" in metrics:
        summary_parts.append(
            f"член семьи: {metrics['secondary_coverage']:g} "
            f"{scope.get('currency', '')}".strip()
        )
    if "trip_days" in metrics:
        summary_parts.append(f"до {metrics['trip_days']:g} дней")
    return _evaluation(
        "dominance", metrics, {key: "higher" for key in metrics},
        ", ".join(summary_parts) or "Подтверждённое страхование", scope=scope,
        reason=("Учитываются сумма, срок, территория и статус подключения. "
                "Покрытия в долларах и евро сопоставляются в рублёвом "
                f"эквиваленте по официальному курсу ЦБ на {INSURANCE_FX_DATE}."),
    )


def _insurance_display(text: str) -> str:
    """Show insured amounts, never PBI's estimated market price of a policy."""
    estimate_pattern = (
        r"(?:и|;)?\s*Примерная стоимость на 2 взрослых\s*≈\s*"
        r"[\d\s]+\s*₽"
    )
    text = re.sub(estimate_pattern, "", text, flags=re.IGNORECASE).rstrip(" ;,.")
    coverage = re.search(
        r"([$€])\s*(\d+(?:[.,]\d+)?)"
        r"(?:\s*/\s*(\d+(?:[.,]\d+)?))?\s*(млн|тыс)?",
        text,
        flags=re.IGNORECASE,
    )
    if not coverage:
        return text
    currency, owner, family, unit = coverage.groups()
    unit_suffix = f" {unit}" if unit else ""
    label = f"Страховое покрытие: {currency}{owner}{unit_suffix}"
    if family is not None:
        label += (
            f" для владельца / {currency}{family}{unit_suffix} "
            "для члена семьи"
        )
    return text[:coverage.start()] + label + text[coverage.end():]


def _service_presence_evaluation(text: str, field: str) -> dict:
    low = text.lower()
    if _explicit_absence(text):
        label = "Не предусмотрено" if field == "concierge" else "Supreme не заявлена"
        return _evaluation(
            "ordinal", {"service_rank": 0}, {"service_rank": "higher"}, label
        )
    if any(marker in low for marker in ("при актив", "при выполн", "покупк от", "может быть")):
        rank, label = 2, "Доступно при выполнении условий"
    elif "бесплат" in low or "включён в пакет" in low or "включен в пакет" in low:
        rank, label = 4, "Бесплатно включено"
    elif re.search(r"(?<!бес)платн", low) or re.search(
        r"(?:стоимост|обслуживан|выпуск)[^.;]{0,28}\d[\d\s]*\s*₽", text,
        flags=re.IGNORECASE,
    ):
        rank, label = 1, "Доступно платно"
    elif _has_benefit(text):
        rank, label = 3, "Наличие подтверждено, стоимость не выделена"
    else:
        return _incomparable_evaluation(
            "Наличие услуги не подтверждено однозначно.", _shorten(text, 110)
        )
    metrics = {"service_rank": rank}
    directions = {"service_rank": "higher"}
    if field == "concierge" and any(marker in low for marker in ("24/7", "круглосуточ")):
        metrics["round_the_clock"] = 1
        directions["round_the_clock"] = "higher"
    extra_cards = re.search(r"до\s*(\d+)\s*дополнительн", low)
    if field == "supreme" and extra_cards:
        metrics["additional_cards"] = float(extra_cards.group(1))
        directions["additional_cards"] = "higher"
    return _evaluation(
        "ordinal", metrics, directions, label,
        reason="Статус наличия, бесплатность и подтверждённые условия сравниваются раздельно.",
    )


def _benefit_key(title: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", " ", title.lower()).strip()


def _benefit_rub_total(description: str):
    """Return a confirmed total when one benefit states count × rubles."""
    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*"
        r"(?:заказ(?:а|ов)?|посещени(?:е|я|й)|поезд(?:ка|ки|ок))"
        r"(?:\s+в\s+месяц)?\s+(?:по|на)\s+"
        r"(\d[\d\s.,]*)\s*(тыс|млн)?\s*₽",
        description,
        flags=re.IGNORECASE,
    )
    if not match:
        promo = re.search(
            r"промокод(?:ы|ов)?\s+на\s+(\d[\d\s.,]*)\s*(тыс|млн)?(?:\s*₽)?",
            description,
            flags=re.IGNORECASE,
        )
        if not promo:
            return None
        amount = _parse_rub_number(promo.group(1))
        if amount is None:
            return None
        unit = (promo.group(2) or "").lower()
        if unit == "тыс":
            amount *= 1000
        elif unit == "млн":
            amount *= 1_000_000
        return amount
    count = _parse_float(match.group(1))
    amount = _parse_rub_number(match.group(2))
    if count is None or amount is None:
        return None
    unit = (match.group(3) or "").lower()
    if unit == "тыс":
        amount *= 1000
    elif unit == "млн":
        amount *= 1_000_000
    return count * amount


def _benefits_evaluation(raw_value, display_value) -> dict:
    source_text = str(raw_value or "")
    raw = _public_text(source_text)
    if _is_missing(raw):
        return _missing_evaluation()
    items = (
        display_value
        if isinstance(display_value, list)
        else _benefits_list(source_text)
    )
    benefits = {}
    labels = {}
    status_rank = {"selectable": 1, "always_included": 2}
    for item in items:
        if item.get("availability") == "rule":
            continue
        key = _benefit_key(item.get("title", ""))
        if not key:
            continue
        availability = item.get("availability", "")
        benefit = {
            "status": status_rank.get(availability, 1),
            "status_known": 1 if availability in status_rank else 0,
        }
        rub_total = _benefit_rub_total(item.get("description", ""))
        if rub_total is not None:
            benefit["rub_total"] = rub_total
        benefits[key] = benefit
        labels[key] = item.get("title", key)
    if not benefits:
        return _incomparable_evaluation(
            "Не найден набор привилегий с подтверждённым статусом.",
            _shorten(raw, 110),
        )
    always_count = sum(
        1 for benefit in benefits.values() if benefit["status"] == 2
    )
    selectable_count = sum(
        1 for benefit in benefits.values() if benefit["status"] == 1
        and benefit["status_known"] == 1
    )
    confirmed_count = sum(
        1 for benefit in benefits.values() if benefit["status_known"] == 0
    )
    summary_parts = [
        f"{always_count} постоянно",
        f"{selectable_count} на выбор",
    ]
    if confirmed_count:
        summary_parts.append(f"{confirmed_count} с подтверждённым наличием")
    summary = ", ".join(summary_parts)
    valued = [
        f"{labels[key]}: {_compact_rub(benefit['rub_total'])}"
        for key, benefit in benefits.items()
        if "rub_total" in benefit
    ]
    if valued:
        summary += f"; {', '.join(valued)}"
    return _evaluation(
        "benefit_set", {"benefits": benefits, "labels": labels}, {}, summary,
        reason=(
            "Наборы сравниваются по подтверждённому наличию одинаковых "
            "привилегий, известному статусу включения и подтверждённому "
            "номиналу одинаковых услуг."
        ),
    )


def _comparison_score(field: str, value: str):
    text = _public_text(value)
    if _is_missing(text):
        return None
    low = text.lower()
    if any(marker in low for marker in ("безлимит", "без ограничений", "не ограничен")):
        if field in {"lounge_access", "taxi", "restaurants", "transfers_payments", "cash_withdrawal"}:
            return 1_000_000
    if field in {"cashback", "deposits"}:
        return _max_percent(text) or _presence_score(text)
    if field == "entry_conditions":
        return _entry_conditions_score(text)
    if field in {"transfers_payments", "cash_withdrawal"}:
        return _limit_score(text) or _presence_score(text)
    if field == "lounge_access":
        return _lounge_score(text) or _presence_score(text)
    if field in {"taxi", "restaurants"}:
        return _compensation_score(text) or _presence_score(text)
    if field == "insurance":
        return _insurance_compare_score(text) or _presence_score(text)
    if field == "concierge":
        return _presence_score(text)
    if field == "supreme":
        return _presence_score(text)
    return None


def _entry_conditions_score(text: str):
    amounts = _rub_amounts(text)
    if not amounts:
        return None
    return -min(amounts)


def _limit_score(text: str):
    low = text.lower()
    if any(marker in low for marker in ("безлимит", "без ограничений", "не ограничен")):
        return 1_000_000_000_000
    amounts = _rub_amounts(text)
    if not amounts:
        return None
    amount = max(amounts)
    # Periods are deliberately not converted: the structured evaluator compares
    # them explicitly and refuses an ambiguous daily/monthly ordering.
    return amount


def _presence_score(text: str):
    return 1 if _has_benefit(text) else 0


def _max_percent(text: str):
    values = [
        float(match.replace(",", "."))
        for match in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", text)
    ]
    return max(values) if values else None


def _rub_amounts(text: str) -> list[float]:
    values = []
    pattern = r"(?<![\d.,])(\d[\d\s.,]*)(?:\s*)(тыс|млн)?(?:\s*)(?:₽|руб)"
    for number, unit in re.findall(pattern, text, flags=re.IGNORECASE):
        amount = _parse_rub_number(number)
        if amount is None:
            continue
        if unit.lower() == "тыс":
            amount *= 1000
        elif unit.lower() == "млн":
            amount *= 1_000_000
        values.append(amount)
    return values


def _parse_rub_number(number: str):
    compact = re.sub(r"\s+", "", number)
    if not compact:
        return None
    if "," in compact or "." in compact:
        separators = [char for char in compact if char in ",."]
        if len(separators) > 1:
            groups = re.split(r"[,.]", compact)
            if groups[0].isdigit() and all(len(group) == 3 and group.isdigit() for group in groups[1:]):
                compact = "".join(groups)
        if "," in compact or "." in compact:
            sep = "," if "," in compact else "."
            head, tail = compact.rsplit(sep, 1)
            if len(tail) == 3 and head.isdigit():
                compact = head + tail
            else:
                compact = compact.replace(",", ".")
    try:
        return float(compact)
    except ValueError:
        return None


def _monthly_counts(text: str) -> list[float]:
    low = text.lower()
    counts = [
        float(n.replace(",", "."))
        for n in re.findall(
            r"(\d+(?:[.,]\d+)?)\s*(?:в мес|/мес|раз(?:а|ов)? в месяц|"
            r"посещени(?:е|я|й) в месяц)", low
        )
    ]
    annual = [count / 12 for count in _annual_counts(text)]
    return counts + annual


def _annual_counts(text: str) -> list[float]:
    low = text.lower()
    return [
        float(n.replace(",", "."))
        for n in re.findall(
            r"(\d+(?:[.,]\d+)?)\s*(?:в год|/год|раз(?:а|ов)? в год|"
            r"посещени(?:е|я|й) в год)", low
        )
    ]


def _lounge_score(text: str):
    counts = _monthly_counts(text)
    if counts:
        return max(counts)
    return None


def _compensation_score(text: str):
    amounts = _rub_amounts(text)
    counts = _monthly_counts(text)
    if not amounts and not counts:
        return None
    # Amount wins first, visit count breaks ties.
    return (max(amounts) if amounts else 0) * 1000 + (max(counts) if counts else 0)


def _insurance_compare_score(text: str):
    low = text.lower()
    amounts = []
    for number, unit in re.findall(r"(\d+(?:[.,]\d+)?)\s*(млн|тыс)?", low):
        try:
            amount = float(number.replace(",", "."))
        except ValueError:
            continue
        if unit == "млн":
            amount *= 1_000_000
        elif unit == "тыс":
            amount *= 1000
        amounts.append(amount)
    days = [
        float(n.replace(",", "."))
        for n in re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:дн|дней|дня)", low)
    ]
    if not amounts and not days:
        return None
    return (max(amounts) if amounts else 0) + (max(days) if days else 0) / 1000


def _is_missing(value: str) -> bool:
    text = (value or "").strip()
    return not text or text == NOT_FOUND or "не найдено" in text.lower()


def _has_benefit(value: str) -> bool:
    text = (value or "").strip()
    if _is_missing(text):
        return False
    low = text.lower()
    if low.startswith(("—", "-")):
        return False
    if low.startswith("нет —") or low.startswith("нет,"):
        return False
    return True


def _format_rub(value) -> str:
    try:
        amount = int(float(value))
    except (TypeError, ValueError):
        return str(value)
    return f"{amount:,}".replace(",", " ")


def _compact_rub(value) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return str(value)
    if amount >= 1_000_000:
        millions = amount / 1_000_000
        if millions.is_integer():
            return f"{int(millions)} млн ₽"
        return f"{millions:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " млн ₽"
    if amount >= 1000 and amount % 1000 == 0:
        return f"{int(amount / 1000)} тыс ₽"
    return f"{_format_rub(amount)} ₽"


def _shorten(value: str, limit: int = 120) -> str:
    return make_complete_summary(value or NOT_FOUND, limit)


def _details(raw: str, summary: str) -> str:
    split = split_summary_and_details(raw, 220)
    details = split["details"]
    if not details:
        return ""
    clean_summary = normalize_source_text(summary)
    return "" if details == clean_summary else details


def _esc(value) -> str:
    return html.escape(_display_text(value))


def _public_text(value) -> str:
    return normalize_source_text(value)


def _display_text(value) -> str:
    text = _public_text(value)
    text = re.sub(r"(\d+)\s+визит\(ов\)/мес", _visit_text, text)
    text = re.sub(r"(\d+)\s+компенсаций/мес суммарно", _compensation_text, text)
    text = re.sub(r"(\d+)\s+опций/подписок упомянуто", _option_text, text)
    replacements = {
        "Excel": "таблица",
        "excel": "таблица",
        "автоматически": "",
        "распознанная метрика": "метрика",
        "распознанный балл": "балл",
        "распознанного": "",
        "распознанной": "",
        "распознано": "выделено",
        "распознан": "выделен",
        "исходные фрагменты": "детали",
        "исходный фрагмент": "детали",
        "безусловное": "",
        "проседает": "ниже",
        "выигрывает": "сильнее",
        "дешевле": "ниже по цене",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def _benefit_display(field: str, raw: str, metric: str) -> str:
    text = _public_text(raw)
    if field == "insurance":
        return _shorten(_insurance_display(text), 230)
    if field in {
        "cashback", "deposits", "taxi", "restaurants",
        "always_included_options", "selectable_options", "selection_rules",
        "auto", "ecosystem", "concierge", "lounge_access",
        "transfers_payments", "cash_withdrawal", "supreme",
    }:
        return _status_prefix(field, text) + _shorten(text, 170)
    return _display_text(metric)


def _benefits_list(raw: str) -> list[dict]:
    if _is_missing(raw):
        return []
    items = []
    for line in str(raw).splitlines():
        line = _public_text(line).strip()
        if not line:
            continue
        if line.lower().startswith("условия выбора:"):
            items.append({
                "title": "Условия выбора",
                "description": line.split(":", 1)[1].strip(),
                "availability": "rule",
            })
            continue
        line = line.lstrip("• ").strip()
        availability = ""
        if "[опция на выбор]" in line.lower():
            availability = "selectable"
            line = re.sub(r"\s*\[опция на выбор\]\s*", "", line,
                          flags=re.IGNORECASE)
        elif "[включено постоянно]" in line.lower():
            availability = "always_included"
            line = re.sub(r"\s*\[включено постоянно\]\s*", "", line,
                          flags=re.IGNORECASE)
        if " — " in line:
            title, description = line.split(" — ", 1)
        else:
            title, description = line, ""
        if title:
            items.append({
                "title": normalize_source_text(title.strip()),
                "description": normalize_source_text(description.strip()),
                "availability": availability,
            })
    return items


def _validate_attr(attr: dict, context: str):
    values = []
    if isinstance(attr.get("value"), list):
        for idx, item in enumerate(attr["value"]):
            values.append((f"{context} / benefit {idx} title", item.get("title", "")))
            values.append((f"{context} / benefit {idx} description", item.get("description", "")))
    else:
        values.append((f"{context} / value", attr.get("value", "")))
    values.append((f"{context} / note", attr.get("note", "")))
    values.append((f"{context} / details", attr.get("details", "")))
    for item_context, text in values:
        if text:
            assert_user_visible_text(str(text), item_context)


def _status_prefix(field: str, text: str) -> str:
    low = text.lower()
    if low.startswith(("опция на выбор:", "включено постоянно:", "общий лимит:")):
        return ""
    if field == "always_included_options":
        return "Включено постоянно: "
    if field == "selectable_options":
        return "Опция на выбор: "
    badges = []
    if "всегда включ" in low:
        badges.append("Включено постоянно")
    if "опция" in low and "всегда включ" not in low:
        badges.append("Опция на выбор")
    if "общий лимит" in low:
        badges.append("Общий лимит")
    return (" · ".join(badges) + ": ") if badges else ""


def _visit_text(match) -> str:
    count = int(match.group(1))
    noun = _ru_plural(count, "визит", "визита", "визитов")
    return f"{count} {noun} в месяц"


def _compensation_text(match) -> str:
    count = int(match.group(1))
    noun = _ru_plural(count, "компенсация", "компенсации", "компенсаций")
    return f"{count} {noun} в месяц"


def _option_text(match) -> str:
    count = int(match.group(1))
    option = _ru_plural(count, "опция", "опции", "опций")
    subscription = _ru_plural(count, "подписка", "подписки", "подписок")
    return f"{count} {option} или {subscription}"


def _ru_plural(count: int, one: str, few: str, many: str) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return one
    elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return few
    return many


# Токен-сет единый с лендингом отзывов (landing/premium_reviews.py):
# белый фон, зелёный акцент, терракот — только для негативного сигнала
# (здесь — меньший итоговый балл в шапке сравнения).
_CSS = """
:root {
  --bg: #F2F5F1;
  --surface: #FFFFFF;
  --card: #FFFFFF;
  --ink: #1A1D1B;
  --muted: #64746b;
  --line: #DDE2DA;
  --line-strong: #C9D0C6;
  --green: #188f4f;
  --green-soft: #188f4f1a;
  --neg: #B3492F;
  --shadow: 0 6px 20px rgba(29, 43, 34, 0.07);
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  -webkit-tap-highlight-color: rgba(24, 143, 79, 0.18);
}
button, summary { touch-action: manipulation; }
button { -webkit-appearance: none; appearance: none; }
.page { max-width: 1160px; margin: 0 auto; padding: 36px 18px 56px; }
.hero { padding: 18px 0 24px; border-bottom: 1px solid var(--line); }
.eyebrow { margin: 0 0 8px; color: var(--green); font-size: 13px;
  font-weight: 700; text-transform: uppercase; }
h1 { margin: 0; font-size: 42px; line-height: 1.08; }
.lead { max-width: 780px; margin: 14px 0 0; color: var(--muted); font-size: 17px; }
.stats { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }
.stats div { min-width: 150px; background: var(--surface);
  border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px;
  box-shadow: var(--shadow); }
.stats b { display: block; font-size: 24px; color: var(--green);
  font-family: ui-monospace, "SF Mono", Menlo, monospace; }
.stats span { color: var(--muted); font-size: 13px; }
.pickers { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px;
  margin-top: 22px; }
.picker { background: var(--surface); border: 1px solid var(--line);
  border-radius: 8px; min-width: 0; padding: 14px 16px;
  box-shadow: var(--shadow); }
.picker h2 { margin: 0 0 10px; font-size: 16px; }
.picker h3 { margin: 12px 0 8px; font-size: 12px; color: var(--muted);
  text-transform: uppercase; }
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { border: 1px solid var(--line); background: var(--surface); color: var(--ink);
  border-radius: 999px; min-height: 44px; padding: 10px 14px; font-size: 14px;
  line-height: 1.2; cursor: pointer; font-family: inherit; }
.level-chip { display: inline-flex; flex-direction: column; align-items: flex-start;
  gap: 2px; text-align: left; border-radius: 12px; }
.chip-main { font-weight: 700; }
.chip-meta { color: var(--muted); font-size: 12px; }
.chip:hover { border-color: var(--green); color: var(--green); }
.chip.active { background: var(--green); border-color: var(--green); color: #fff; }
.chip.active .chip-meta { color: rgba(255, 255, 255, 0.84); }
.recommendations { margin-top: 16px; padding: 16px; border: 1px solid var(--line);
  border-radius: 8px; background: var(--surface); box-shadow: var(--shadow); }
.recommendations-head { display: flex; align-items: end; justify-content: space-between;
  gap: 16px; margin-bottom: 12px; }
.recommendations-kicker { margin: 0 0 2px; color: var(--green); font-size: 11px;
  font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
.recommendations h2 { margin: 0; font-size: 20px; }
.recommendations-summary { max-width: 620px; margin: 0; color: var(--muted);
  font-size: 13px; text-align: right; }
.recommendation-grid { display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 8px; }
.recommendation-card { display: flex; min-width: 0; min-height: 116px;
  flex-direction: column; align-items: flex-start; gap: 5px; padding: 12px;
  border: 1px solid var(--line); border-radius: 8px; background: #fff;
  color: var(--ink); cursor: pointer; text-align: left; font: inherit; }
.recommendation-card:hover:not(:disabled),
.recommendation-card:focus-visible:not(:disabled) { border-color: var(--green);
  box-shadow: 0 0 0 2px rgba(24, 143, 79, 0.12); outline: 0; }
.recommendation-card:disabled { cursor: default; opacity: .55; }
.recommendation-bank { color: var(--green); font-size: 12px; font-weight: 800; }
.recommendation-tier { font-size: 14px; font-weight: 750; line-height: 1.3; }
.recommendation-threshold { color: var(--muted); font-size: 12px; }
.recommendation-match { margin-top: auto; padding: 3px 7px; border-radius: 999px;
  background: var(--green-soft); color: var(--green); font-size: 11px;
  font-weight: 750; }
.recommendation-card.nearest .recommendation-match { background: #fff8e8;
  color: #795f1e; }
.recommendation-empty { grid-column: 1 / -1; margin: 0; padding: 12px;
  border-radius: 8px; background: #f7f9f5; color: var(--muted); font-size: 13px; }
.hint { margin: 18px 0 0; color: var(--muted); }
.js-warning { margin: 14px 0 0; padding: 12px 14px; border: 1px solid var(--line);
  border-radius: 8px; background: #fff8e8; color: #6f5a25; font-size: 14px; }
.js-ready .js-warning { display: none; }
.compare-actions { display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-bottom: 12px; }
.print-title, .print-date { display: none; }
.pdf-button { min-height: 44px; border: 1px solid var(--green);
  border-radius: 8px; background: var(--green); color: #fff; cursor: pointer;
  padding: 10px 14px; font: inherit; font-weight: 700; }
.pdf-button:hover, .pdf-button:focus-visible { background: #0f7a41;
  border-color: #0f7a41; outline: 2px solid rgba(24, 143, 79, 0.24);
  outline-offset: 2px; }
.pdf-button:disabled { cursor: wait; opacity: 0.72; }
#compare {
  --compare-level-count: 3;
  --compare-attr-column: minmax(8.5rem, 0.38fr);
  --compare-level-column: minmax(0, 1fr);
  --compare-grid-template:
    var(--compare-attr-column)
    repeat(var(--compare-level-count), var(--compare-level-column));
  --compare-cell-padding: 10px 12px;
  margin-top: 22px;
}
.cmp-head {
  display: grid;
  grid-template-columns: var(--compare-grid-template);
  gap: 0;
}
.cmp-attr-spacer { min-width: 0; }
.cmp-col { background: var(--surface); border: 1px solid var(--line-strong);
  border-top: 3px solid var(--green); border-radius: 8px; min-width: 0;
  padding: 14px 16px; box-shadow: var(--shadow); }
.cmp-col h2 { margin: 2px 0 6px; font-size: 20px; }
.cmp-entry-hint { margin: -2px 0 0; color: var(--muted); font-size: 13px; }
.cmp-col .sc { font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 26px; color: var(--green); font-weight: 700; }
.cmp-col .sc.lower { color: var(--neg); }
.cmp-col .sc small { font-size: 12px; color: var(--muted); font-weight: 400; }
.method { margin: 12px 0 0; color: var(--muted); font-size: 13px; }
.method summary { cursor: pointer; font-weight: 700; color: var(--ink); }
.method p { margin: 6px 0 0; max-width: 900px; }
.cmp-scroll { margin-top: 12px; max-height: 62vh; overflow: auto;
  border: 1px solid var(--line-strong); border-radius: 8px;
  background: var(--surface); box-shadow: var(--shadow); }
.cmp-table { display: block; width: 100%; border-collapse: separate; border-spacing: 0; }
.cmp-table thead,
.cmp-table tbody { display: block; }
.cmp-table tr {
  display: grid;
  grid-template-columns: var(--compare-grid-template);
}
.cmp-table th, .cmp-table td { text-align: left; padding: 10px 12px;
  border-bottom: 1px solid var(--line); vertical-align: top; font-size: 14px;
  min-width: 0; overflow-wrap: anywhere; }
.cmp-table td:not(:first-child) { white-space: pre-line; }
.cmp-table thead th { background: #F7F9F5;
  color: var(--muted); font-size: 12px; text-transform: uppercase; z-index: 1;
  box-shadow: 0 1px 0 var(--line); }
.cmp-table td:first-child { color: var(--muted); font-size: 13px;
  white-space: normal; }
.cmp-table td.rank-best, .cmp-table td.win { box-shadow: inset 3px 0 0 #2e9b62;
  background: #f0faf4; }
.cmp-table td.rank-mid { box-shadow: inset 3px 0 0 #d7a51d;
  background: #fff9e8; }
.cmp-table td.rank-low { box-shadow: inset 3px 0 0 #d16d5d;
  background: #fff3f1; }
.cmp-table td .tag { display: inline-block; margin-left: 6px;
  background: var(--green-soft); color: var(--green); border-radius: 999px;
  padding: 1px 8px; font-size: 11px; font-weight: 700; }
.cmp-table td.rank-best .tag, .cmp-table td.win .tag {
  background: #e3f4ea; color: #187347; }
.cmp-table td.rank-mid .tag { background: #fff0bf; color: #806010; }
.cmp-table td.rank-low .tag { background: #ffe2de; color: #9b3d31; }
.cmp-table td .rank-reason { display: block; margin-top: 5px; color: var(--muted);
  font-size: 11px; line-height: 1.35; white-space: normal; }
.benefits-list { list-style: none; margin: 0; padding: 0; display: grid;
  gap: 7px; }
.benefits-list li { position: relative; padding-left: 0; }
.benefit-title { font-weight: 700; }
.benefit-description { color: var(--ink); }
.tag.selectable { background: #fff4df; color: #8a5a00; }
.tag.always { background: var(--green-soft); color: var(--green); }
.benefit-rule { margin-top: 8px; color: var(--muted); font-size: 13px; }
.attr-details { margin-top: 8px; color: var(--muted); font-size: 13px; }
.attr-details summary { cursor: pointer; color: var(--green); font-weight: 700; }
.attr-details p { margin: 6px 0 0; color: var(--ink); white-space: normal; }
.pdf-exporting #compare { width: 1120px; margin: 0; background: #fff; color: #111; }
.pdf-exporting .compare-actions { display: block; margin: 0 0 10px; }
.pdf-exporting .compare-actions .pdf-button { display: none; }
.pdf-exporting .print-title { display: block; margin: 0; font-size: 24px;
  line-height: 1.2; font-weight: 800; color: #111; }
.pdf-exporting .print-date { display: block; margin: 4px 0 0; color: #4f5c55; }
.pdf-exporting .cmp-scroll { max-height: none; overflow: visible; box-shadow: none; }
.pdf-exporting .cmp-col { box-shadow: none; }
.pdf-exporting .attr-details summary { display: none; }
.footer { margin-top: 40px; padding-top: 18px; border-top: 1px solid var(--line);
  color: var(--muted); font-size: 13px; }
@media (max-width: 820px) {
  .page { padding: 24px 14px 42px; }
  h1 { font-size: 32px; }
  .stats div { flex: 1 1 138px; min-width: 0; }
  .pickers, .cmp-head { grid-template-columns: 1fr; }
  .cmp-attr-spacer { display: none; }
  .picker, .recommendations { padding: 14px; }
  .recommendations-head { display: block; }
  .recommendations-summary { margin-top: 6px; text-align: left; }
  .recommendation-grid { grid-template-columns: 1fr; }
  .recommendation-card { min-height: 0; }
  .chip-row { gap: 8px; }
  .chip { flex: 1 1 auto; justify-content: center; min-width: min(46%, 220px); }
  .level-chip { align-items: center; min-width: min(100%, 220px); text-align: center; }
  .cmp-scroll { max-height: none; overflow: visible; border: 0; border-radius: 0; }
  .cmp-table, .cmp-table colgroup, .cmp-table tbody, .cmp-table tr,
  .cmp-table td { display: block; width: 100%; }
  .cmp-table thead { display: none; }
  .cmp-table tr { margin-bottom: 14px; border: 1px solid var(--line-strong);
    border-radius: 8px; background: var(--surface); overflow: hidden;
    box-shadow: var(--shadow); }
  .cmp-table td { border-bottom: 1px solid var(--line); padding: 11px 12px;
    white-space: normal; }
  .cmp-table td:first-child { background: #F7F9F5; font-weight: 700;
    color: var(--ink); font-size: 14px; }
  .cmp-table td:last-child { border-bottom: 0; }
  .cmp-table td[data-label]::before { content: attr(data-label); display: block;
    margin-bottom: 4px; color: var(--muted); font-size: 12px; font-weight: 700; }
  .cmp-table td.rank-best, .cmp-table td.win { box-shadow: inset 3px 0 0 #2e9b62; }
  .cmp-table td.rank-mid { box-shadow: inset 3px 0 0 #d7a51d; }
  .cmp-table td.rank-low { box-shadow: inset 3px 0 0 #d16d5d; }
}
@media print {
  @page { size: A4 landscape; margin: 10mm; }
  :root {
    --bg: #fff;
    --surface: #fff;
    --line: #d4d8d2;
    --line-strong: #b8c0b5;
    --green-soft: #eef7f2;
  }
  body { background: #fff; color: #111; font-size: 10px; line-height: 1.35; }
  .page { max-width: none; margin: 0; padding: 0; }
  .hero, .pickers, .recommendations, #hint,
  #js-warning, .footer,
  .compare-actions .pdf-button {
    display: none !important;
  }
  #compare { display: block !important; margin: 0; }
  .compare-actions { display: block; margin: 0 0 8px; }
  .print-title { display: block; margin: 0; font-size: 18px; line-height: 1.2;
    font-weight: 800; color: #111; }
  .print-date { display: block; margin: 3px 0 0; color: #4f5c55; font-size: 10px; }
  .cmp-scroll { max-height: none; overflow: visible; margin-top: 8px;
    border: 1px solid var(--line-strong); border-radius: 0; box-shadow: none; }
  .cmp-head { break-inside: avoid; page-break-inside: avoid; }
  .cmp-col { border-radius: 0; box-shadow: none; padding: 7px 8px;
    border-top-width: 2px; }
  .cmp-col h2 { margin: 0; font-size: 12px; line-height: 1.25; }
  .cmp-entry-hint { margin: 2px 0 0; font-size: 8px; color: #4f5c55; }
  .cmp-table, .cmp-table thead, .cmp-table tbody { display: block !important; }
  .cmp-table tr { display: grid !important; grid-template-columns: var(--compare-grid-template); }
  .cmp-table thead { display: block !important; }
  .cmp-table th, .cmp-table td { padding: 5px 6px; font-size: 9px;
    line-height: 1.28; color: #111; overflow-wrap: anywhere; word-break: normal; }
  .cmp-table thead th { color: #4f5c55; font-size: 8px; box-shadow: none; }
  .cmp-table td:first-child { color: #4f5c55; font-size: 8px; font-weight: 700; }
  .cmp-table tr { break-inside: avoid; page-break-inside: avoid; }
  .cmp-table td.rank-best, .cmp-table td.win {
    background: #f0faf4; box-shadow: inset 2px 0 0 #2e9b62; }
  .cmp-table td.rank-mid {
    background: #fff9e8; box-shadow: inset 2px 0 0 #d7a51d; }
  .cmp-table td.rank-low {
    background: #fff3f1; box-shadow: inset 2px 0 0 #d16d5d; }
  .cmp-table td .tag { border: 1px solid #cfe1d6; padding: 0 4px; font-size: 7px;
    background: #f5faf7; color: #146c40; }
  .benefits-list { gap: 3px; }
  .benefit-rule, .attr-details, .attr-details p, .cmp-table td .rank-reason {
    font-size: 8px; color: #4f5c55; }
  .attr-details summary { display: none; }
  .attr-details p { margin: 3px 0 0; color: #111; }
}
"""

_JS = """
const DATA = JSON.parse(document.getElementById('data').textContent);
const SIDES = ['a', 'b', 'c'];
const ALWAYS_SHOW_FIELDS = new Set(['transfers_payments', 'cash_withdrawal', 'supreme']);
const HTML2CANVAS_URL = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
const JSPDF_URL = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
let pdfLibraryPromise = null;
const state = Object.fromEntries(SIDES.map((side) => [side, { bank: null, level: null }]));
document.documentElement.classList.add('js-ready');

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderBanks(side) {
  const picker = document.querySelector(`.picker[data-side="${side}"]`);
  const row = picker.querySelector('.banks');
  row.querySelectorAll('.chip').forEach((chip) => {
    const i = Number(chip.dataset.bankIndex);
    if (state[side].bank === i) chip.classList.add('active');
    else chip.classList.remove('active');
    chip.onclick = () => {
      state[side].bank = i;
      state[side].level = null;
      renderBanks(side);
      renderLevels(side);
      renderRecommendations();
      renderCompare();
    };
  });
}

function renderLevels(side) {
  const picker = document.querySelector(`.picker[data-side="${side}"]`);
  const title = picker.querySelector('.lvl-title');
  const row = picker.querySelector('.levels');
  row.innerHTML = '';
  const bankIdx = state[side].bank;
  title.hidden = bankIdx === null;
  if (bankIdx === null) return;
  DATA[bankIdx].levels.forEach((lvl, i) => {
    const chip = el('button', 'chip level-chip');
    chip.type = 'button';
    chip.appendChild(el('span', 'chip-main', lvl.tier));
    if (lvl.entry_hint) chip.appendChild(el('span', 'chip-meta', `(${lvl.entry_hint})`));
    if (state[side].level === i) chip.classList.add('active');
    chip.onclick = () => {
      state[side].level = i;
      renderLevels(side);
      renderRecommendations();
      renderCompare();
      if (side === 'a') scrollToRecommendations();
    };
    row.appendChild(chip);
  });
}

function scrollToRecommendations() {
  const section = document.getElementById('recommendations');
  if (section.hidden) return;
  const reduceMotion = window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  section.scrollIntoView({
    behavior: reduceMotion ? 'auto' : 'smooth',
    block: 'start'
  });
}

function selected(side) {
  const s = state[side];
  if (s.bank === null || s.level === null) return null;
  return { bank: DATA[s.bank].bank, ...DATA[s.bank].levels[s.level] };
}

function validEntryMatch(level) {
  const match = level && level.entry_match;
  return Boolean(match && match.eligible
    && Number.isFinite(Number(match.min_amount))
    && Number.isFinite(Number(match.max_amount)));
}

function intervalDistance(left, right) {
  const leftMin = Number(left.min_amount);
  const leftMax = Number(left.max_amount);
  const rightMin = Number(right.min_amount);
  const rightMax = Number(right.max_amount);
  if (leftMax < rightMin) return rightMin - leftMax;
  if (rightMax < leftMin) return leftMin - rightMax;
  return 0;
}

function recommendationKind(reference, candidate) {
  const sameScalar = Number(reference.min_amount) === Number(reference.max_amount)
    && Number(candidate.min_amount) === Number(candidate.max_amount)
    && Number(reference.min_amount) === Number(candidate.min_amount);
  if (sameScalar) return { id: 'exact', rank: 0, label: 'Точное совпадение' };
  const distance = intervalDistance(reference, candidate);
  if (distance === 0) {
    return { id: 'overlap', rank: 1, label: 'Подходит по диапазону' };
  }
  const direction = Number(candidate.max_amount) < Number(reference.min_amount)
    ? 'ниже' : 'выше';
  return {
    id: 'nearest', rank: 2,
    label: `На ${formatRub(distance)} ${direction}`
  };
}

function formatRub(amount) {
  const value = Number(amount);
  if (!Number.isFinite(value)) return '';
  if (value >= 1000000) {
    const millions = value / 1000000;
    return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 })
      .format(millions)} млн ₽`;
  }
  if (value >= 1000 && value % 1000 === 0) {
    return `${new Intl.NumberFormat('ru-RU').format(value / 1000)} тыс ₽`;
  }
  return `${new Intl.NumberFormat('ru-RU').format(value)} ₽`;
}

function buildRecommendations(referenceBankIndex, referenceLevel) {
  const reference = referenceLevel.entry_match;
  const recommendations = [];
  DATA.forEach((bank, bankIndex) => {
    if (bankIndex === referenceBankIndex) return;
    const candidates = bank.levels
      .map((level, levelIndex) => {
        if (!validEntryMatch(level)) return null;
        const kind = recommendationKind(reference, level.entry_match);
        return {
          bank: bank.bank,
          bankIndex,
          level,
          levelIndex,
          distance: intervalDistance(reference, level.entry_match),
          width: Number(level.entry_match.max_amount)
            - Number(level.entry_match.min_amount),
          kind
        };
      })
      .filter(Boolean)
      .sort((left, right) => left.kind.rank - right.kind.rank
        || left.distance - right.distance
        || left.width - right.width
        || left.levelIndex - right.levelIndex);
    if (candidates.length) recommendations.push(candidates[0]);
  });
  return recommendations.sort((left, right) => left.kind.rank - right.kind.rank
    || left.distance - right.distance
    || left.bank.localeCompare(right.bank, 'ru'));
}

function nextRecommendationSide() {
  return ['b', 'c'].find((side) => state[side].bank === null
    || state[side].level === null) || null;
}

function applyRecommendation(recommendation) {
  const side = nextRecommendationSide();
  if (!side) return;
  state[side].bank = recommendation.bankIndex;
  state[side].level = recommendation.levelIndex;
  renderBanks(side);
  renderLevels(side);
  renderRecommendations();
  renderCompare();
}

function renderRecommendations() {
  const section = document.getElementById('recommendations');
  const summary = document.getElementById('recommendations-summary');
  const list = document.getElementById('recommendations-list');
  const referenceState = state.a;
  if (referenceState.bank === null || referenceState.level === null) {
    section.hidden = true;
    list.innerHTML = '';
    return;
  }

  section.hidden = false;
  list.innerHTML = '';
  const referenceLevel = DATA[referenceState.bank].levels[referenceState.level];
  if (!validEntryMatch(referenceLevel)) {
    summary.textContent = 'Автоматический подбор доступен для уровней '
      + 'с подтверждённым условием по капиталу или остатку.';
    list.appendChild(el('p', 'recommendation-empty',
      'У выбранного уровня нет отдельного подтверждённого порога капитала. '
      + 'Банки 2 и 3 можно выбрать вручную.'));
    return;
  }

  summary.textContent = `Ориентир: ${referenceLevel.entry_match.label}. `
    + 'Сначала показаны точные совпадения, затем ближайшие уровни.';
  const recommendations = buildRecommendations(referenceState.bank, referenceLevel);
  if (!recommendations.length) {
    list.appendChild(el('p', 'recommendation-empty',
      'В доступных данных нет других уровней с подтверждённым порогом капитала.'));
    return;
  }

  const selectedBanks = new Set(['b', 'c']
    .map((side) => state[side].bank)
    .filter((bankIndex) => bankIndex !== null));
  const slotsFull = nextRecommendationSide() === null;
  recommendations.forEach((recommendation) => {
    const alreadySelected = selectedBanks.has(recommendation.bankIndex);
    const card = el('button', `recommendation-card ${recommendation.kind.id}`);
    card.type = 'button';
    card.disabled = alreadySelected || slotsFull;
    card.appendChild(el('span', 'recommendation-bank', recommendation.bank));
    card.appendChild(el('span', 'recommendation-tier', recommendation.level.tier));
    card.appendChild(el('span', 'recommendation-threshold',
      `Вход: ${recommendation.level.entry_match.label}`));
    let matchLabel = recommendation.kind.label;
    if (alreadySelected) matchLabel += ' · Уже выбран';
    else if (slotsFull) matchLabel += ' · Места заполнены';
    card.appendChild(el('span', 'recommendation-match', matchLabel));
    card.onclick = () => applyRecommendation(recommendation);
    list.appendChild(card);
  });
}

function renderHead(node, item) {
  node.innerHTML = '';
  node.appendChild(el('h2', '', item.bank + ' — ' + item.tier));
  if (item.entry_hint) node.appendChild(el('p', 'cmp-entry-hint', `Вход: ${item.entry_hint}`));
}

function renderCompare() {
  const selectedItems = SIDES
    .map((side) => ({ side, item: selected(side) }))
    .filter((entry) => entry.item);
  const cmp = document.getElementById('compare');
  const hint = document.getElementById('hint');
  if (selectedItems.length < SIDES.length) {
    cmp.hidden = true;
    hint.hidden = false;
    return;
  }
  cmp.hidden = false; hint.hidden = true;
  cmp.style.setProperty('--compare-level-count', String(selectedItems.length));

  SIDES.forEach((side) => {
    const entry = selectedItems.find((item) => item.side === side);
    const head = cmp.querySelector(`[data-head="${side}"]`);
    const th = cmp.querySelector(`[data-th="${side}"]`);
    renderHead(head, entry.item);
    th.textContent = entry.item.bank + ' — ' + entry.item.tier;
  });

  const tbody = cmp.querySelector('tbody');
  tbody.innerHTML = '';
  selectedItems[0].item.attrs.forEach((baseAttr, i) => {
    const attrsBySide = Object.fromEntries(
      selectedItems.map((entry) => [entry.side, entry.item.attrs[i]])
    );
    const selectedAttrs = selectedItems.map((entry) => attrsBySide[entry.side]);
    if (!ALWAYS_SHOW_FIELDS.has(baseAttr.id)
        && selectedAttrs.every((attr) => isEmptyDisplay(attr.value))) return;
    const tr = el('tr');
    const labelCell = el('td', '', baseAttr.label);
    tr.appendChild(labelCell);

    const cellsBySide = {};
    SIDES.forEach((side) => {
      const td = el('td');
      const entry = selectedItems.find((item) => item.side === side);
      const attr = attrsBySide[side];
      renderAttrValue(td, attr);
      td.dataset.label = entry.item.bank + ' — ' + entry.item.tier;
      if (attr.note) td.title = attr.note;
      cellsBySide[side] = td;
      tr.appendChild(td);
    });

    highlightWinners(selectedItems, attrsBySide, cellsBySide);
    tbody.appendChild(tr);
  });
  cmp.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function loadPdfScript(url, ready) {
  if (ready()) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = url;
    script.async = true;
    script.onload = () => ready()
      ? resolve()
      : reject(new Error(`PDF dependency did not initialize: ${url}`));
    script.onerror = () => reject(new Error(`PDF dependency failed to load: ${url}`));
    document.head.appendChild(script);
  });
}

function loadPdfLibrary() {
  if (window.html2canvas && window.jspdf && window.jspdf.jsPDF) {
    return Promise.resolve({ html2canvas: window.html2canvas, jsPDF: window.jspdf.jsPDF });
  }
  if (pdfLibraryPromise) return pdfLibraryPromise;
  pdfLibraryPromise = Promise.all([
    loadPdfScript(HTML2CANVAS_URL, () => Boolean(window.html2canvas)),
    loadPdfScript(JSPDF_URL, () => Boolean(window.jspdf && window.jspdf.jsPDF))
  ]).then(() => ({ html2canvas: window.html2canvas, jsPDF: window.jspdf.jsPDF }));
  return pdfLibraryPromise;
}

function comparePdfFileName() {
  const parts = SIDES
    .map((side) => selected(side))
    .filter(Boolean)
    .map((item) => item.bank + ' ' + item.tier);
  const name = 'premium-comparison-' + parts.join('-vs-');
  return name
    .toLowerCase()
    .replace(/[^a-zа-яё0-9]+/gi, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 120) + '.pdf';
}

function pdfCaptureSizeForElement(element) {
  const rect = element.getBoundingClientRect();
  const widthPx = Math.ceil(Math.max(element.scrollWidth, element.offsetWidth, rect.width));
  const heightPx = Math.ceil(Math.max(element.scrollHeight, element.offsetHeight, rect.height));
  const maxCanvasSide = 16000;
  return {
    widthPx,
    heightPx,
    scale: Math.min(2, maxCanvasSide / widthPx, maxCanvasSide / heightPx)
  };
}

async function exportComparePdf() {
  const cmp = document.getElementById('compare');
  if (!cmp || cmp.hidden) return;
  const button = document.getElementById('pdf-button');
  const originalText = button.textContent;
  const openedDetails = [];
  cmp.querySelectorAll('details').forEach((details) => {
    if (!details.open) {
      details.open = true;
      openedDetails.push(details);
    }
  });
  const restore = () => {
    openedDetails.forEach((details) => { details.open = false; });
    document.body.classList.remove('pdf-exporting');
    button.disabled = false;
    button.textContent = originalText;
  };
  button.disabled = true;
  button.textContent = 'Готовлю PDF...';
  document.body.classList.add('pdf-exporting');
  try {
    const { html2canvas, jsPDF } = await loadPdfLibrary();
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(
      () => requestAnimationFrame(resolve)
    ));
    const marginMm = 8;
    const captureSize = pdfCaptureSizeForElement(cmp);
    const canvas = await html2canvas(cmp, {
      scale: captureSize.scale,
      useCORS: true,
      backgroundColor: '#ffffff',
      width: captureSize.widthPx,
      height: captureSize.heightPx,
      windowWidth: Math.max(document.documentElement.clientWidth, captureSize.widthPx)
    });
    const pdf = new jsPDF({
      unit: 'mm',
      format: 'a3',
      orientation: 'landscape',
      compress: true
    });
    const sheetWidth = pdf.internal.pageSize.getWidth();
    const sheetHeight = pdf.internal.pageSize.getHeight();
    const availableWidth = sheetWidth - marginMm * 2;
    const availableHeight = sheetHeight - marginMm * 2;
    const fit = Math.min(
      availableWidth / canvas.width,
      availableHeight / canvas.height
    );
    const imageWidth = canvas.width * fit;
    const imageHeight = canvas.height * fit;
    const imageX = (sheetWidth - imageWidth) / 2;
    const imageY = marginMm;
    pdf.addImage(
      canvas.toDataURL('image/jpeg', 0.98),
      'JPEG', imageX, imageY, imageWidth, imageHeight, undefined, 'FAST'
    );
    pdf.save(comparePdfFileName());
  } catch (error) {
    console.error('PDF export failed', error);
    const detail = error && error.message ? `\n${error.message}` : '';
    window.alert(`Не удалось подготовить PDF. Повторите выгрузку.${detail}`);
  } finally {
    restore();
  }
}

function highlightWinners(selectedItems, attrsBySide, cellsBySide) {
  const entries = selectedItems.map((entry) => ({
    side: entry.side,
    attr: attrsBySide[entry.side],
    evaluation: attrsBySide[entry.side].evaluation || {
      status: 'missing', reason: 'Нет структурированной оценки.'
    }
  }));
  const results = rankEvaluations(entries);
  results.forEach((result) => {
    const cell = cellsBySide[result.side];
    const attr = attrsBySide[result.side];
    cell.dataset.evaluationStatus = result.status;
    const explanation = [attr.note, result.reason].filter(Boolean).join('\\n');
    if (explanation) cell.title = explanation;
    if (!result.cls) return;
    cell.classList.add(result.cls);
    cell.appendChild(el('span', 'tag rank-tag', result.label));
    if (result.summary) {
      cell.appendChild(el('span', 'rank-reason', result.summary));
    }
  });
}

function rankEvaluations(entries) {
  const results = new Map(entries.map((entry) => [entry.side, {
    side: entry.side,
    status: isMissingRankEntry(entry) ? 'missing' : entry.evaluation.status,
    reason: entry.evaluation.reason || 'Для условия нет структурированного пояснения.'
  }]));
  const available = entries.filter(
    (entry) => !isMissingRankEntry(entry)
  );
  if (!available.length) return entries.map((entry) => results.get(entry.side));

  if (available.every((entry) => entry.evaluation.status === 'comparable')) {
    const totals = new Map(available.map((entry) => [entry.side, 0]));
    let structuredOrder = true;
    for (let i = 0; i < available.length && structuredOrder; i += 1) {
      for (let j = i + 1; j < available.length; j += 1) {
        const comparison = compareEvaluations(
          available[i].evaluation, available[j].evaluation
        );
        if (comparison.order === null) {
          structuredOrder = false;
          break;
        }
        totals.set(
          available[i].side, totals.get(available[i].side) + comparison.order
        );
        totals.set(
          available[j].side, totals.get(available[j].side) - comparison.order
        );
      }
    }
    if (structuredOrder) {
      return applyVisualRanks(
        entries, available, results,
        new Map(available.map((entry) => [entry.side, [totals.get(entry.side)]])),
        false
      );
    }
  }

  const vectors = new Map(
    available.map((entry) => [entry.side, fallbackRankVector(entry)])
  );
  return applyVisualRanks(entries, available, results, vectors, true);
}

function applyVisualRanks(entries, available, results, vectors, fallbackUsed) {
  const uniqueVectors = [];
  available.forEach((entry) => {
    const vector = vectors.get(entry.side);
    if (!uniqueVectors.some((candidate) => deepEqual(candidate, vector))) {
      uniqueVectors.push(vector);
    }
  });
  uniqueVectors.sort((left, right) => -compareRankVectors(left, right));

  if (available.length === 1) {
    const entry = available[0];
    results.set(entry.side, rankedResult(
      entry, { cls: 'rank-best', label: 'сильнее' }, false, fallbackUsed
    ));
    return entries.map((item) => results.get(item.side));
  }

  const visualRanks = uniqueVectors.length === 1
    ? [{ cls: 'rank-mid', label: 'среднее' }]
    : uniqueVectors.length === 2
    ? [
        { cls: 'rank-best', label: 'сильнее' },
        { cls: 'rank-low', label: 'слабее' }
      ]
    : [
        { cls: 'rank-best', label: 'сильнее' },
        { cls: 'rank-mid', label: 'среднее' },
        { cls: 'rank-low', label: 'слабее' }
      ];
  available.forEach((entry) => {
    const vector = vectors.get(entry.side);
    const groupIndex = uniqueVectors.findIndex(
      (candidate) => deepEqual(candidate, vector)
    );
    const groupSize = available.filter(
      (candidate) => deepEqual(vectors.get(candidate.side), vector)
    ).length;
    results.set(
      entry.side,
      rankedResult(entry, visualRanks[groupIndex], groupSize > 1, fallbackUsed)
    );
  });
  return entries.map((entry) => results.get(entry.side));
}

function rankedResult(entry, visual, equal, fallbackUsed) {
  const fallbackReason = fallbackUsed
    ? 'Для обязательного ранга применены приоритетные показатели этой категории.'
    : '';
  return {
    side: entry.side,
    status: equal ? 'equal' : 'comparable',
    cls: visual.cls,
    label: visual.label,
    summary: entry.evaluation.summary,
    reason: [entry.evaluation.reason, fallbackReason].filter(Boolean).join(' ')
  };
}

function compareRankVectors(left, right) {
  const length = Math.max(left.length, right.length);
  for (let i = 0; i < length; i += 1) {
    const leftValue = Number(left[i] ?? 0);
    const rightValue = Number(right[i] ?? 0);
    if (leftValue === rightValue) continue;
    return leftValue > rightValue ? 1 : -1;
  }
  return 0;
}

function fallbackRankVector(entry) {
  const attr = entry.attr || {};
  const evaluation = entry.evaluation || {};
  const metrics = evaluation.metrics || {};
  const metric = (key, defaultValue = 0) => {
    const value = Number(metrics[key]);
    return Number.isFinite(value) ? value : defaultValue;
  };
  const legacy = Number(attr.score);
  const legacyScore = attr.score !== null && attr.score !== undefined
    && Number.isFinite(legacy) ? legacy : null;

  if (attr.id === 'entry_conditions') {
    const capitalKeys = [
      'capital', 'capital_moscow', 'capital_regions', 'joint_capital', 'special_assets'
    ];
    const capitalValues = capitalKeys
      .map((key) => Number(metrics[key]))
      .filter((value) => Number.isFinite(value) && value > 0);
    const spend = metric('monthly_spend', Number.MAX_SAFE_INTEGER);
    const income = metric('monthly_income', Number.MAX_SAFE_INTEGER);
    if (capitalValues.length) {
      return [2, -Math.min(...capitalValues), -Math.max(...capitalValues), 0];
    }
    if ((Number.isFinite(spend) && spend < Number.MAX_SAFE_INTEGER)
        || (Number.isFinite(income) && income < Number.MAX_SAFE_INTEGER)) {
      return [3, -spend, -income, 0];
    }
    const monthlyFee = legacyScore !== null ? Math.abs(legacyScore) : Number.MAX_SAFE_INTEGER;
    return [4, -monthlyFee, 0, 0];
  }
  if (attr.id === 'service_cost') {
    return [metric('service_rank'), -metric('monthly_cost')];
  }
  if (attr.id === 'transfers_payments' || attr.id === 'cash_withdrawal') {
    if (metrics.unlimited) return [1, 0, 0];
    const periodRank = { year: 1, billing: 2, month: 3, operation: 3, day: 4 };
    const limits = metrics.limits || [];
    const strongest = limits.reduce((best, item) => {
      if (!best || item.amount > best.amount) return item;
      if (item.amount === best.amount
          && (periodRank[item.period] || 0) > (periodRank[best.period] || 0)) return item;
      return best;
    }, null);
    return strongest
      ? [0, Number(strongest.amount) || 0, periodRank[strongest.period] || 0]
      : [0, legacyScore ?? 0, 0];
  }
  if (attr.id === 'lounge_access') {
    const annualVisits = metric('annual_cap', metric('visits_monthly') * 12);
    return [metric('unlimited'), annualVisits, metric('visits_monthly'),
      metric('availability'), metric('guests')];
  }
  if (attr.id === 'cashback') {
    const rateKnown = Number.isFinite(Number(metrics.max_rate)) ? 1 : 0;
    return [rateKnown, metric('base_rate'), metric('max_rate'),
      metric('unlimited_accrual'), metric('bonus_rub_value'),
      metric('monthly_cap'), metric('monthly_bonus_cap'), metric('categories')];
  }
  if (attr.id === 'deposits') {
    return [metric('rate', legacyScore ?? 0), -metric('minimum_amount'), metric('maximum_amount')];
  }
  if (attr.id === 'taxi' || attr.id === 'restaurants') {
    return [metric('unlimited'), metric('annual_total'), metric('monthly_total'),
      metric('per_use_limit'), metric('monthly_count'), metric('annual_count'),
      metric('availability')];
  }
  if (attr.id === 'insurance') {
    return [metric('coverage_rub', metric('coverage')),
      metric('secondary_coverage_rub', metric('secondary_coverage')),
      metric('trip_days'), metric('availability')];
  }
  if (attr.id === 'concierge' || attr.id === 'supreme') {
    return [metric('service_rank', legacyScore ?? 0), metric('round_the_clock'),
      metric('additional_cards')];
  }
  if (attr.id === 'other_benefits') {
    const items = Array.isArray(attr.value) ? attr.value : [];
    const always = items.filter((item) => item.availability === 'always_included').length;
    const selectable = items.filter((item) => item.availability === 'selectable').length;
    const confirmed = items.filter((item) => item.availability !== 'rule').length;
    const benefitValues = Object.values(metrics.benefits || {});
    const rubTotal = benefitValues.reduce(
      (total, item) => total + (Number(item.rub_total) || 0), 0
    );
    return [confirmed, rubTotal, always, selectable];
  }
  return [legacyScore ?? 0];
}

function isMissingRankEntry(entry) {
  if (entry.evaluation.status === 'missing') return true;
  const value = entry.attr ? entry.attr.value : '';
  if (Array.isArray(value)) return value.length === 0;
  const text = String(value || '').trim().toLowerCase();
  return !text || text.includes('не найдено') || text.includes('не нашли')
    || text === 'нет данных';
}

function compareEvaluations(left, right) {
  if (left.method !== right.method) {
    return { order: null, reason: 'используются разные методы оценки.' };
  }
  if (!deepEqual(left.scope || {}, right.scope || {})) {
    return { order: null, reason: 'различается область действия условий.' };
  }
  if (left.method === 'limit') return compareLimits(left, right);
  if (left.method === 'lounge') return compareLounges(left, right);
  if (left.method === 'benefit_set') return compareBenefitSets(left, right);
  if (left.method === 'ordinal') return compareOrdinal(left, right);
  if (left.method === 'dominance') return compareDominance(left, right);
  return { order: null, reason: 'для условий нет доказуемого порядка.' };
}

function compareLounges(left, right) {
  const leftUnlimited = Boolean(left.metrics.unlimited);
  const rightUnlimited = Boolean(right.metrics.unlimited);
  let visitOrder = 0;
  if (leftUnlimited !== rightUnlimited) {
    visitOrder = leftUnlimited ? 1 : -1;
  } else if (!leftUnlimited) {
    const leftVisits = Number(left.metrics.visits_monthly);
    const rightVisits = Number(right.metrics.visits_monthly);
    if (!Number.isFinite(leftVisits) || !Number.isFinite(rightVisits)) {
      return { order: null, reason: 'не у всех вариантов подтверждено количество посещений.' };
    }
    visitOrder = leftVisits === rightVisits ? 0 : leftVisits > rightVisits ? 1 : -1;
  }
  const omit = new Set(['unlimited', 'visits_monthly']);
  const leftOther = Object.fromEntries(
    Object.entries(left.metrics).filter(([key]) => !omit.has(key))
  );
  const rightOther = Object.fromEntries(
    Object.entries(right.metrics).filter(([key]) => !omit.has(key))
  );
  const directions = Object.fromEntries(
    Object.keys(leftOther).map((key) => [key, 'higher'])
  );
  const other = compareDominance(
    { metrics: leftOther, directions },
    { metrics: rightOther, directions: Object.fromEntries(
      Object.keys(rightOther).map((key) => [key, 'higher'])
    ) }
  );
  if (other.order === null) return other;
  if (visitOrder && other.order && visitOrder !== other.order) {
    return { order: null, reason: 'число посещений и дополнительные условия дают разных лидеров.' };
  }
  return { order: visitOrder || other.order, reason: '' };
}

function compareOrdinal(left, right) {
  const leftRank = Number(left.metrics.service_rank);
  const rightRank = Number(right.metrics.service_rank);
  if (Number.isFinite(leftRank) && Number.isFinite(rightRank) && leftRank !== rightRank) {
    return { order: leftRank > rightRank ? 1 : -1, reason: '' };
  }
  return compareDominance(left, right);
}

function compareDominance(left, right) {
  const leftKeys = Object.keys(left.metrics || {}).sort();
  const rightKeys = Object.keys(right.metrics || {}).sort();
  if (!deepEqual(leftKeys, rightKeys)) {
    return { order: null, reason: 'набор существенных параметров различается.' };
  }
  let leftBetter = false;
  let rightBetter = false;
  for (const key of leftKeys) {
    const leftValue = Number(left.metrics[key]);
    const rightValue = Number(right.metrics[key]);
    const direction = left.directions[key];
    if (!Number.isFinite(leftValue) || !Number.isFinite(rightValue)
        || direction !== right.directions[key]) {
      return { order: null, reason: 'метрики нельзя привести к общей шкале.' };
    }
    if (leftValue === rightValue) continue;
    const leftWins = direction === 'lower'
      ? leftValue < rightValue
      : leftValue > rightValue;
    if (leftWins) leftBetter = true;
    else rightBetter = true;
  }
  if (leftBetter && rightBetter) {
    return { order: null, reason: 'каждый вариант лучше по разным параметрам.' };
  }
  if (leftBetter) return { order: 1, reason: '' };
  if (rightBetter) return { order: -1, reason: '' };
  return { order: 0, reason: '' };
}

function compareLimits(left, right) {
  if (left.metrics.unlimited || right.metrics.unlimited) {
    if (left.metrics.unlimited && right.metrics.unlimited) return { order: 0, reason: '' };
    return { order: left.metrics.unlimited ? 1 : -1, reason: '' };
  }
  const leftLimits = left.metrics.limits || [];
  const rightLimits = right.metrics.limits || [];
  if (leftLimits.length === 1 && rightLimits.length === 1) {
    return compareSingleLimit(leftLimits[0], rightLimits[0]);
  }
  const leftByPeriod = Object.fromEntries(leftLimits.map((item) => [item.period, item.amount]));
  const rightByPeriod = Object.fromEntries(rightLimits.map((item) => [item.period, item.amount]));
  const periods = Object.keys(leftByPeriod).sort();
  if (!deepEqual(periods, Object.keys(rightByPeriod).sort())) {
    return { order: null, reason: 'набор дневных и месячных лимитов различается.' };
  }
  return compareDominance(
    {
      metrics: leftByPeriod,
      directions: Object.fromEntries(periods.map((period) => [period, 'higher']))
    },
    {
      metrics: rightByPeriod,
      directions: Object.fromEntries(periods.map((period) => [period, 'higher']))
    }
  );
}

function compareSingleLimit(left, right) {
  if (left.period === right.period) {
    if (left.amount === right.amount) return { order: 0, reason: '' };
    return { order: left.amount > right.amount ? 1 : -1, reason: '' };
  }
  if (left.period === 'day' && right.period === 'month') {
    return left.amount >= right.amount
      ? { order: 1, reason: '' }
      : { order: null, reason: 'суточный лимит меньше месячного, поэтому преимущество зависит от сценария.' };
  }
  if (left.period === 'month' && right.period === 'day') {
    return right.amount >= left.amount
      ? { order: -1, reason: '' }
      : { order: null, reason: 'месячный лимит больше суточного, поэтому преимущество зависит от сценария.' };
  }
  return { order: null, reason: 'лимиты указаны за разные несопоставимые периоды.' };
}

function compareBenefitSets(left, right) {
  const leftBenefits = left.metrics.benefits || {};
  const rightBenefits = right.metrics.benefits || {};
  const leftKeys = new Set(Object.keys(leftBenefits));
  const rightKeys = new Set(Object.keys(rightBenefits));
  const leftContainsRight = [...rightKeys].every((key) => leftKeys.has(key));
  const rightContainsLeft = [...leftKeys].every((key) => rightKeys.has(key));

  function compareBenefitValue(containerValue, containedValue) {
    let containerBetter = false;
    let containedBetter = false;
    const containerStatus = Number(containerValue.status);
    const containedStatus = Number(containedValue.status);
    if (containerStatus !== containedStatus) {
      if (containerStatus > containedStatus) containerBetter = true;
      else containedBetter = true;
    }
    const containerRub = Number(containerValue.rub_total);
    const containedRub = Number(containedValue.rub_total);
    const containerHasRub = Number.isFinite(containerRub);
    const containedHasRub = Number.isFinite(containedRub);
    if (containerHasRub !== containedHasRub) return null;
    if (containerHasRub && containerRub !== containedRub) {
      if (containerRub > containedRub) containerBetter = true;
      else containedBetter = true;
    }
    if (containerBetter && containedBetter) return null;
    if (containerBetter) return 1;
    if (containedBetter) return -1;
    return 0;
  }

  function containsWithoutWeaker(container, contained) {
    return Object.keys(contained).every((key) => {
      if (container[key] === undefined) return false;
      const comparison = compareBenefitValue(container[key], contained[key]);
      return comparison !== null && comparison >= 0;
    });
  }

  const leftDominates = leftContainsRight
    && containsWithoutWeaker(leftBenefits, rightBenefits);
  const rightDominates = rightContainsLeft
    && containsWithoutWeaker(rightBenefits, leftBenefits);
  if (leftDominates && rightDominates && deepEqual(leftBenefits, rightBenefits)) {
    return { order: 0, reason: '' };
  }
  if (leftDominates && !rightDominates) return { order: 1, reason: '' };
  if (rightDominates && !leftDominates) return { order: -1, reason: '' };
  return { order: null, reason: 'наборы привилегий различаются по составу или статусу.' };
}

function deepEqual(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function isEmptyDisplay(value) {
  if (Array.isArray(value)) return value.length === 0;
  const text = String(value || '').toLowerCase();
  return !text || text === 'не найдено' || text.includes('не найдено');
}

function renderAttrValue(cell, attr) {
  if (attr.kind === 'benefits' && Array.isArray(attr.value)) {
    renderBenefits(cell, attr.value);
    appendDetails(cell, attr);
    return;
  }
  cell.textContent = attr.value;
  appendDetails(cell, attr);
}

function appendDetails(cell, attr) {
  if (!attr.details || attr.details === attr.value) return;
  const details = el('details', 'attr-details');
  details.appendChild(el('summary', '', 'Подробнее'));
  details.appendChild(el('p', '', attr.details));
  cell.appendChild(details);
}

function renderBenefits(cell, items) {
  const listItems = items.filter((item) => item.availability !== 'rule');
  const rule = items.find((item) => item.availability === 'rule');
  if (!listItems.length && !rule) {
    cell.textContent = 'Не найдено в доступных источниках';
    return;
  }
  if (listItems.length) {
    const ul = el('ul', 'benefits-list');
    listItems.forEach((item) => {
      const li = el('li');
      li.appendChild(el('span', 'benefit-title', item.title));
      if (item.description) {
        li.appendChild(document.createTextNode(' — '));
        li.appendChild(el('span', 'benefit-description', item.description));
      }
      if (item.availability === 'selectable') {
        li.appendChild(document.createTextNode(' '));
        li.appendChild(el('span', 'tag selectable', 'Опция на выбор'));
      } else if (item.availability === 'always_included'
          && hasMixedBenefitStatuses(listItems)) {
        li.appendChild(document.createTextNode(' '));
        li.appendChild(el('span', 'tag always', 'Включено постоянно'));
      }
      ul.appendChild(li);
    });
    cell.appendChild(ul);
  }
  if (rule && rule.description) {
    cell.appendChild(el('div', 'benefit-rule',
      'Условия выбора: ' + rule.description));
  }
}

function hasMixedBenefitStatuses(items) {
  const statuses = new Set(items
    .map((item) => item.availability)
    .filter((status) => status && status !== 'unknown'));
  return statuses.size > 1;
}

SIDES.forEach((side) => {
  renderBanks(side);
});
renderRecommendations();
document.getElementById('pdf-button').addEventListener('click', exportComparePdf);
initChangesApp(document.querySelector('.changes-app'));
initChangesPanel(document.querySelector('.js-changes-panel'));
"""
