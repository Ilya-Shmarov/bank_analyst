# -*- coding: utf-8 -*-
"""Static Sber-vs-market landing generated from the Excel summary sheet."""

import html
import re
from pathlib import Path

from openpyxl import load_workbook

from scanner.scoring import SCORERS
from scanner.sources import NOT_FOUND

SUMMARY_SHEET = "Сводная"
INTL_SEGMENT = "digital-first (межд.)"
SBER_TIER_PREFIXES = (
    "СберПремьер",
    "СберПервый",
    "Sber Private Banking",
)

BASE_COLUMNS = {
    "segment": "Сегмент капитала",
    "bank": "Банк",
    "tier": "Тир",
    "scan_date": "Дата скана",
    "sources_ok": "Источников OK",
    "score": "Итоговый балл (0–5)",
    "divergent": "Расхождение источников",
}

FIELD_COLUMNS = {
    "entry_conditions": "Условия входа / поддержания уровня",
    "service_cost": "Стоимость обслуживания",
    "lounge_access": "Бизнес-залы (визиты, спутники)",
    "concierge": "Консьерж-сервис",
    "cashback": "Кэшбэк (ставка, категории, механика)",
    "deposits": "Спецусловия по вкладам / накопительным счетам",
    "insurance": "Страхование (мед., ВЗР)",
    "auto": "Автоуслуги",
    "taxi_restaurants": "Такси и рестораны (компенсации)",
    "ecosystem": "Экосистемные привилегии (доставка, подписки)",
}

FIELD_LABELS = {
    "score": "Итоговый балл",
    "service_cost": "Стоимость",
    "lounge_access": "Бизнес-залы",
    "concierge": "Консьерж",
    "cashback": "Кэшбэк",
    "deposits": "Вклады",
    "insurance": "Страхование",
    "auto": "Авто",
    "taxi_restaurants": "Такси и рестораны",
    "ecosystem": "Экосистема",
}

SCORED_FIELDS = tuple(SCORERS)
CARD_FIELDS = (
    "score",
    "service_cost",
    "lounge_access",
    "concierge",
    "cashback",
    "deposits",
    "insurance",
    "auto",
    "taxi_restaurants",
    "ecosystem",
)


def build_sber_vs_landing(workbook_path: Path, output_path: Path) -> dict:
    """Build the static Sber-vs-market landing page."""
    rows = load_summary_rows(workbook_path)
    comparisons = build_comparisons(rows)
    html_text = render_html(comparisons)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")

    competitor_keys = {
        (row["bank"], row["tier"])
        for comp in comparisons
        for row in comp["competitors"]
    }
    return {
        "output": str(output_path),
        "sber_tiers": len(comparisons),
        "competitor_rows": len(competitor_keys),
    }


def load_summary_rows(workbook_path: Path) -> list[dict]:
    """Read normalized banking rows from the workbook summary sheet."""
    if not workbook_path.exists():
        raise FileNotFoundError(
            f"Excel report not found: {workbook_path}. Run --scan-all first."
        )

    wb = load_workbook(workbook_path, read_only=True, data_only=True)
    if SUMMARY_SHEET not in wb.sheetnames:
        raise ValueError(f'Sheet "{SUMMARY_SHEET}" not found in {workbook_path}.')

    ws = wb[SUMMARY_SHEET]
    headers = {
        _clean(cell.value): idx
        for idx, cell in enumerate(next(ws.iter_rows(min_row=1, max_row=1)), start=1)
    }
    _require_headers(headers, [*BASE_COLUMNS.values(), *FIELD_COLUMNS.values()])

    rows = []
    current_segment = ""
    for cells in ws.iter_rows(min_row=2, values_only=True):
        raw_segment = _clean(cells[headers[BASE_COLUMNS["segment"]] - 1])
        bank = _clean(cells[headers[BASE_COLUMNS["bank"]] - 1])
        tier = _clean(cells[headers[BASE_COLUMNS["tier"]] - 1])
        if raw_segment and not bank:
            current_segment = raw_segment
            continue
        if not bank or not tier:
            continue

        row = {
            key: _clean(cells[headers[column] - 1])
            for key, column in BASE_COLUMNS.items()
        }
        row["segment"] = row["segment"] or current_segment
        row["score"] = _parse_float(row["score"])
        row["fields"] = {
            key: _clean(cells[headers[column] - 1])
            for key, column in FIELD_COLUMNS.items()
        }
        if row["segment"] and row["segment"] != INTL_SEGMENT:
            rows.append(row)
    return rows


def build_comparisons(rows: list[dict]) -> list[dict]:
    """Build Sber tier comparisons against same-segment Russian competitors."""
    sber_rows = [
        row for row in rows
        if row["bank"] == "Сбер" and row["tier"].startswith(SBER_TIER_PREFIXES)
    ]
    comparisons = []
    for sber in sber_rows:
        competitors = [
            row for row in rows
            if row["bank"] != "Сбер" and row["segment"] == sber["segment"]
        ]
        avg_score = _average(row["score"] for row in competitors)
        best = _best_by_score(competitors)

        comparisons.append({
            "sber": sber,
            "competitors": sorted(
                competitors,
                key=lambda row: (row["score"] is None, -(row["score"] or 0), row["bank"]),
            ),
            "avg_score": avg_score,
            "best_competitor": best,
            "cards": _comparison_cards(sber, competitors, avg_score, best),
        })
    return comparisons


def render_html(comparisons: list[dict]) -> str:
    """Render a complete standalone HTML document."""
    scan_dates = sorted({
        comp["sber"]["scan_date"][:10] for comp in comparisons
        if comp["sber"].get("scan_date")
    })
    latest_scan = scan_dates[-1] if scan_dates else "нет данных"
    competitor_total = len({
        (row["bank"], row["tier"])
        for comp in comparisons
        for row in comp["competitors"]
    })

    sections = "\n".join(_render_section(comp) for comp in comparisons)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Сбер VS остальные банки</title>
  <style>{_CSS}</style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="eyebrow">Премиальный банкинг РФ</p>
      <h1>Сбер VS остальные банки</h1>
      <p class="lead">Сравнение премиальных пакетов по уровням капитала:
      кто сильнее по итоговому баллу, условиям обслуживания и ключевым
      привилегиям.</p>
      <div class="stats">
        <div><b>{len(comparisons)}</b><span>уровней Сбера</span></div>
        <div><b>{competitor_total}</b><span>конкурентных тиров</span></div>
        <div><b>{_esc(latest_scan)}</b><span>дата данных</span></div>
      </div>
    </section>
    {sections}
  </main>
</body>
</html>"""


def _require_headers(headers: dict, required: list[str]):
    missing = [header for header in required if header not in headers]
    if missing:
        raise ValueError(
            f"Missing required columns in sheet \"{SUMMARY_SHEET}\": "
            + ", ".join(missing)
        )


def _comparison_cards(sber: dict, competitors: list[dict], avg_score, best) -> list[dict]:
    cards = [_score_card(sber, avg_score, best), _service_conditions_card(sber, best)]
    cards.extend(_field_card(field, sber, competitors) for field in SCORED_FIELDS)
    return [card for card in cards if card is not None]


def _score_card(sber: dict, avg_score, best) -> dict:
    sber_score = sber["score"]
    best_score = best["score"] if best else None
    if sber_score is None:
        return _card(
            kind="unknown",
            field="score",
            title="Итоговый балл",
            summary="Недостаточно данных, чтобы сравнить итоговый балл этого уровня.",
            sber_value="нет данных",
            competitor_value=_metric_label(best) if best else "нет данных",
            competitor_row=best,
            details=_score_details(sber, best),
        )
    if best_score is None or sber_score >= best_score:
        kind = "sber" if best_score is None or sber_score > best_score else "parity"
        summary = (
            f"Сбер набирает {sber_score:.2f}; средний балл конкурентов — "
            f"{_format_score(avg_score)}."
        )
        if kind == "parity" and best:
            summary = (
                f"Сбер на уровне лидера сегмента по итоговому баллу: "
                f"{sber_score:.2f} против {best_score:.2f}."
            )
        return _card(
            kind=kind,
            field="score",
            title="Итоговый балл",
            summary=summary,
            sber_value=f"{sber_score:.2f}",
            competitor_value=_metric_label(best),
            competitor_row=best,
            details=_score_details(sber, best),
        )
    summary = (
        f"По итоговому баллу сильнее {_row_label(best)}: {best_score:.2f}. "
        f"У Сбера — {sber_score:.2f}; средний балл конкурентов — {_format_score(avg_score)}."
    )
    return _card(
        kind="competitor",
        field="score",
        title="Итоговый балл",
        summary=summary,
        sber_value=f"{sber_score:.2f}",
        competitor_value=f"{best_score:.2f}",
        competitor_row=best,
        details=_score_details(sber, best),
    )


def _service_conditions_card(sber: dict, score_leader) -> dict:
    sber_cost = _service_cost_summary(sber)
    leader_cost = _service_cost_summary(score_leader) if score_leader else None
    if leader_cost is None:
        return _card(
            kind="unknown",
            field="service_cost",
            title="Стоимость и условия",
            summary="Недостаточно данных, чтобы сопоставить условия обслуживания с лидером сегмента.",
            sber_value=_service_value(sber_cost),
            competitor_value="нет данных",
            competitor_row=None,
            competitor_label="Конкурент",
            details=_service_details(sber, None),
        )

    summary = _service_summary(sber_cost, leader_cost)
    return _card(
        kind="parity",
        field="service_cost",
        title="Стоимость и условия",
        summary=summary,
        sber_value=_service_value(sber_cost),
        competitor_value=_service_value(leader_cost),
        competitor_row=score_leader,
        competitor_label="Конкурент",
        details=_service_details(sber, score_leader),
    )


def _field_card(field: str, sber: dict, competitors: list[dict]) -> dict:
    label = FIELD_LABELS[field]
    sber_metric = _field_metric(field, sber)
    leaders = _field_leaders(field, competitors)
    if not leaders:
        return _card(
            kind="unknown",
            field=field,
            title=label,
            summary=f"Недостаточно данных, чтобы сравнить поле «{label}» с конкурентами.",
            sber_value=_metric_value(sber_metric),
            competitor_value="нет данных",
            competitor_row=None,
            competitor_label="Конкурент",
            details=_field_details(label, sber_metric, None),
        )

    leader = leaders[0]
    leader_score = leader["metric"]["score"]
    sber_score = sber_metric["score"]
    leader_names = _join_rows([item["row"] for item in leaders])

    if sber_score > leader_score:
        summary = (
            f"По направлению «{label}» сильнее Сбер: {_metric_value(sber_metric)}. "
            f"У ближайшего конкурента {leader_names} — {_metric_value(leader['metric'])}."
        )
        return _card(
            kind="sber",
            field=field,
            title=label,
            summary=summary,
            sber_value=_metric_value(sber_metric),
            competitor_value=_metric_value(leader["metric"]),
            competitor_row=leader["row"],
            competitor_label="Конкурент",
            details=_field_details(label, sber_metric, leader["metric"]),
        )

    if sber_score == leader_score and sber_score > 0:
        summary = (
            f"По направлению «{label}» паритет: у Сбера и лидеров одинаковая оценка "
            f"{_format_metric_score(sber_score)}, но условия отличаются."
        )
        return _card(
            kind="parity",
            field=field,
            title=label,
            summary=summary,
            sber_value=_metric_value(sber_metric),
            competitor_value=_metric_value(leader["metric"]),
            competitor_row=leader["row"],
            competitor_label="Конкурент",
            details=_field_details(label, sber_metric, leader["metric"]),
        )

    if sber_score == leader_score == 0:
        summary = (
            f"По направлению «{label}» нет явного лидера: у Сбера и конкурентов "
            f"нет подтвержденного преимущества."
        )
        return _card(
            kind="unknown",
            field=field,
            title=label,
            summary=summary,
            sber_value=_metric_value(sber_metric),
            competitor_value=_metric_value(leader["metric"]),
            competitor_row=leader["row"],
            competitor_label="Конкурент",
            details=_field_details(label, sber_metric, leader["metric"]),
        )

    summary = (
        f"По направлению «{label}» сильнее {leader_names}: "
        f"{_metric_value(leader['metric'])}. У Сбера — {_metric_value(sber_metric)}."
    )
    return _card(
        kind="competitor",
        field=field,
        title=label,
        summary=summary,
        sber_value=_metric_value(sber_metric),
        competitor_value=_metric_value(leader["metric"]),
        competitor_row=leader["row"],
        competitor_label="Конкурент",
        details=_field_details(label, sber_metric, leader["metric"]),
    )


def _card(kind: str, field: str, title: str, summary: str,
          sber_value: str, competitor_value: str, competitor_row,
          competitor_label: str = "Конкурент", details: str = "") -> dict:
    return {
        "kind": kind,
        "field": field,
        "title": title,
        "summary": summary,
        "sber_value": sber_value,
        "competitor_value": competitor_value,
        "competitor": _row_label(competitor_row) if competitor_row else "нет данных",
        "sber_label": "Сбер",
        "competitor_label": competitor_label,
        "details": details,
    }


def _service_cost_summary(row) -> dict:
    if not row:
        return {"status": "unknown", "display": "нет данных", "conditions": "нет данных"}
    raw = row["fields"].get("service_cost", "")
    entry = row["fields"].get("entry_conditions", "")
    conditions = _shorten(entry, 220)
    combined_low = f"{raw} {entry}".lower()
    parts = []
    status = "unknown"
    if "бесплат" in combined_low or re.search(r"\b0\s*(?:₽|руб)", combined_low, flags=re.IGNORECASE):
        parts.append("бесплатно при выполнении условий")
        status = "conditional_free"
    cost = _monthly_rub_cost(raw)
    if cost is not None and cost > 0 and not parts and entry and not _is_missing(entry):
        parts.append("бесплатно при выполнении условий")
        status = "conditional_free"
    if cost is not None and cost > 0:
        parts.append(f"{_format_rub(cost)} ₽ в месяц")
        status = "conditional_or_paid" if status == "conditional_free" else "paid"
    if not parts and _is_missing(raw):
        parts.append("стоимость не указана")
    if not parts and raw:
        parts.append(_shorten(raw, 140))
    if not parts:
        parts.append("нет данных")
    else:
        parts[0] = parts[0][0].upper() + parts[0][1:]
    return {
        "status": status,
        "display": " или ".join(parts),
        "conditions": conditions or "условия не указаны",
        "raw": raw,
        "entry": entry,
    }


def _field_metric(field: str, row: dict) -> dict:
    if field == "score":
        score = row.get("score")
        return {
            "field": field,
            "row": row,
            "metric": _format_score(score),
            "score": score,
            "raw": _format_score(score),
        }
    if field == "service_cost":
        raw = row["fields"].get("service_cost", "")
        cost = _monthly_rub_cost(raw)
        if cost is None:
            return {"field": field, "row": row, "metric": "нет данных", "score": None, "raw": raw}
        # Lower cost is better; invert it into a comparable score.
        return {
            "field": field,
            "row": row,
            "metric": f"{_format_rub(cost)} ₽ в месяц",
            "score": -cost,
            "raw": raw,
        }

    raw = row["fields"].get(field, "")
    if _is_missing(raw):
        return {"field": field, "row": row, "metric": "нет данных", "score": 0, "raw": raw}
    if raw.strip().startswith(("—", "-")):
        return {"field": field, "row": row, "metric": "не предусмотрено", "score": 0, "raw": raw}
    try:
        metric, score = SCORERS[field](raw)
    except Exception:  # noqa: BLE001 — noisy Excel text should not break the landing
        metric, score = ("есть, детали не выделены", 1) if _has_benefit(raw) else ("нет", 0)
    return {"field": field, "row": row, "metric": _display_text(metric), "score": score, "raw": raw}


def _field_leaders(field: str, competitors: list[dict]) -> list[dict]:
    metrics = [
        {"row": row, "metric": _field_metric(field, row)}
        for row in competitors
    ]
    metrics = [item for item in metrics if item["metric"]["score"] is not None]
    if not metrics:
        return []
    best_score = max(item["metric"]["score"] for item in metrics)
    return [item for item in metrics if item["metric"]["score"] == best_score]


def _metric_value(metric: dict) -> str:
    score = metric.get("score")
    score_text = ""
    if isinstance(score, (int, float)):
        score_text = f" ({_format_metric_score(score)})"
    return f"{metric.get('metric') or 'нет данных'}{score_text}"


def _format_metric_score(score) -> str:
    if score is None:
        return "нет данных"
    if isinstance(score, float) and not score.is_integer():
        return f"{score:.2f}/5"
    return f"{int(score)}/5"


def _score_details(sber: dict, competitor) -> str:
    parts = [f"Сбер: {_format_score(sber.get('score'))}."]
    if competitor:
        parts.append(f"{_row_label(competitor)}: {_format_score(competitor.get('score'))}.")
    return " ".join(parts)


def _service_summary(sber_cost: dict, leader_cost: dict) -> str:
    sber_free = _condition_summary(sber_cost.get("conditions", ""))
    leader_free = _condition_summary(leader_cost.get("conditions", ""))
    sber_paid = _paid_part(sber_cost.get("display", ""))
    leader_paid = _paid_part(leader_cost.get("display", ""))
    if sber_free and leader_free:
        sber_text = f"У Сбера бесплатный сценарий: {sber_free}"
        if sber_paid:
            sber_text += f"; платный сценарий — {sber_paid}"
        leader_text = f"У конкурента бесплатный сценарий: {leader_free}"
        if leader_paid:
            leader_text += f"; платный сценарий — {leader_paid}"
        return f"{sber_text}. {leader_text}."
    if sber_free:
        return f"У Сбера бесплатный сценарий: {sber_free}; у конкурента условия раскрыты иначе."
    if leader_free:
        return f"У конкурента бесплатный сценарий: {leader_free}; у Сбера условия раскрыты иначе."
    return "Недостаточно данных, чтобы связно сопоставить условия обслуживания."


def _service_value(cost: dict) -> str:
    conditions = _condition_summary(cost.get("conditions", ""))
    paid = _paid_part(cost.get("display", ""))
    parts = []
    if conditions:
        parts.append(f"Бесплатно при условиях: {conditions}")
    elif "бесплатно" in cost.get("display", "").lower():
        parts.append("Бесплатно при выполнении условий")
    if paid:
        parts.append(f"Платный сценарий: {paid}")
    if not parts:
        parts.append(cost.get("display", "нет данных"))
    return ". ".join(parts)


def _service_details(sber: dict, competitor) -> str:
    parts = [
        "Сбер. Стоимость: "
        f"{sber['fields'].get('service_cost') or NOT_FOUND}. "
        "Условия: "
        f"{sber['fields'].get('entry_conditions') or NOT_FOUND}."
    ]
    if competitor:
        parts.append(
            f"{_row_label(competitor)}. Стоимость: "
            f"{competitor['fields'].get('service_cost') or NOT_FOUND}. "
            "Условия: "
            f"{competitor['fields'].get('entry_conditions') or NOT_FOUND}."
        )
    return " ".join(parts)


def _condition_summary(value: str, limit: int = 5) -> str:
    text = _public_text(value)
    if not text or _is_missing(text):
        return ""
    text = re.sub(r"\s*;\s*", " | ", text)
    text = re.sub(r"\s+\|\s+или\s+\|", " | ", text)
    text = re.sub(r"\|\s*или\s*\|", "|", text)
    text = re.sub(r"\s+", " ", text).strip(" |;")
    parts = []
    for part in re.split(r"\s*\|\s*", text):
        cleaned = part.strip(" ;")
        if not cleaned:
            continue
        if cleaned.lower().startswith("или "):
            cleaned = cleaned[4:].strip()
        low = cleaned.lower()
        if re.search(r"\d[\d\s]*\s*₽\s*в\s*мес", low):
            continue
        if "последний календарный день" in low:
            continue
        if "среднемесячный остаток" in low and parts:
            continue
        if cleaned.lower() in {"или"}:
            continue
        if cleaned and cleaned not in parts:
            parts.append(cleaned)
    if not parts:
        return text
    shown = parts[:limit]
    summary = "; ".join(shown)
    if len(parts) > limit:
        summary += f"; ещё {len(parts) - limit}"
    return summary


def _paid_part(value: str) -> str:
    text = _public_text(value)
    match = re.search(r"(\d[\d\s]*)\s*₽\s+в\s+месяц", text)
    return f"{match.group(1).strip()} ₽ в месяц" if match else ""


def _field_details(label: str, sber_metric: dict, competitor_metric) -> str:
    parts = [
        f"Сбер, {label}: {sber_metric.get('raw') or NOT_FOUND}."
    ]
    if competitor_metric:
        parts.append(
            f"{_row_label(competitor_metric['row'])}, {label}: "
            f"{competitor_metric.get('raw') or NOT_FOUND}."
        )
    return " ".join(parts)


def _render_section(comp: dict) -> str:
    sber = comp["sber"]
    best = comp["best_competitor"]
    best_text = (
        f"{best['bank']} / {best['tier']} ({best['score']:.2f})"
        if best and best["score"] is not None else "нет данных"
    )
    competitor_rows = "\n".join(_render_competitor_row(row) for row in comp["competitors"])
    cards = "".join(_render_card(card) for card in comp["cards"])
    raw_details = "".join(_render_raw_detail(key, sber["fields"].get(key, ""))
                          for key in FIELD_COLUMNS)

    return f"""
    <section class="tier">
      <div class="tier-head">
        <div>
          <p class="segment">{_esc(sber['segment'])}</p>
          <h2>{_esc(sber['tier'])}</h2>
        </div>
        <div class="score">
          <span>Итоговый балл</span>
          <b>{_format_score(sber['score'])}</b>
        </div>
      </div>
      <div class="panel facts">
        <h3>Срез сегмента</h3>
        <p><b>{len(comp['competitors'])}</b> конкурентных тиров</p>
        <p>Средний балл: <b>{_format_score(comp['avg_score'])}</b></p>
        <p>Лидер по баллу: <b>{_esc(best_text)}</b></p>
      </div>
      <h3 class="block-title">Сравнение по ключевым условиям</h3>
      <div class="cards">{cards}</div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Банк</th>
              <th>Тир</th>
              <th>Балл</th>
              <th>Стоимость</th>
              <th>Сильные стороны пакета</th>
            </tr>
          </thead>
          <tbody>{competitor_rows}</tbody>
        </table>
      </div>
      <details class="raw">
        <summary>Детали по Сберу</summary>
        {raw_details}
      </details>
    </section>"""


def _render_card(card: dict) -> str:
    label = {
        "sber": "Сильнее Сбер",
        "parity": "Паритет",
        "competitor": "Сильнее конкурент",
        "unknown": "Недостаточно данных",
    }[card["kind"]]
    competitor_value = card["competitor_value"]
    if card["competitor"] != "нет данных":
        competitor_value = f"{card['competitor']}: {competitor_value}"
    details = ""
    if card.get("details"):
        details = f"""
          <details class="card-details">
            <summary>Детали</summary>
            <p>{_esc(card['details'])}</p>
          </details>"""
    return f"""
        <article class="compare-card {card['kind']}">
          <div class="card-top">
            <span>{_esc(label)}</span>
            <b>{_esc(card['title'])}</b>
          </div>
          <p><b>Подытог:</b> {_esc(card['summary'])}</p>
          <dl>
            <div><dt>{_esc(card['sber_label'])}</dt><dd>{_esc(card['sber_value'])}</dd></div>
            <div><dt>{_esc(card['competitor_label'])}</dt><dd>{_esc(competitor_value)}</dd></div>
          </dl>
          {details}
        </article>"""


def _render_competitor_row(row: dict) -> str:
    cost = _service_cost_summary(row)["display"]
    notes = _competitor_notes(row)
    return f"""
            <tr>
              <td>{_esc(row['bank'])}</td>
              <td>{_esc(row['tier'])}</td>
              <td>{_format_score(row['score'])}</td>
              <td>{_esc(cost)}</td>
              <td>{_esc(notes)}</td>
            </tr>"""


def _competitor_notes(row: dict) -> str:
    metrics = [_field_metric(field, row) for field in SCORED_FIELDS]
    metrics = [m for m in metrics if m["score"] and m["score"] > 0]
    metrics.sort(key=lambda item: item["score"], reverse=True)
    notes = [
        f"{FIELD_LABELS[m['field']]}: {_metric_value(m)}"
        for m in metrics[:3]
    ]
    return "; ".join(notes) or "нет выделенных преимуществ"


def _render_raw_detail(key: str, value: str) -> str:
    return f"""
        <details>
          <summary>{_esc(FIELD_COLUMNS[key])}</summary>
          <p>{_esc(value or NOT_FOUND)}</p>
        </details>"""


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


def _average(values):
    nums = [value for value in values if value is not None]
    return sum(nums) / len(nums) if nums else None


def _best_by_score(rows: list[dict]):
    scored = [row for row in rows if row["score"] is not None]
    return max(scored, key=lambda row: row["score"]) if scored else None


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


def _has_conditions(cost: dict) -> bool:
    text = f"{cost.get('display', '')} {cost.get('conditions', '')}".lower()
    markers = (
        "услов",
        "остат",
        "трат",
        "зарплат",
        "инвест",
        "млн",
        "тыс",
        "portfolio",
        "balance",
    )
    return any(marker in text for marker in markers)


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


def _metric_label(row) -> str:
    if not row:
        return "нет данных"
    return _format_score(row.get("score"))


def _row_label(row) -> str:
    if not row:
        return "нет данных"
    return f"{row['bank']} / {row['tier']}"


def _join_rows(rows: list[dict], limit: int = 3) -> str:
    labels = [_row_label(row) for row in rows[:limit]]
    if len(rows) > limit:
        labels.append(f"ещё {len(rows) - limit}")
    return ", ".join(labels) if labels else "нет данных"


def _format_score(value) -> str:
    return "нет данных" if value is None else f"{value:.2f}"


def _format_rub(value) -> str:
    try:
        amount = int(float(value))
    except (TypeError, ValueError):
        return str(value)
    return f"{amount:,}".replace(",", " ")


def _shorten(value: str, limit: int = 120) -> str:
    text = " ".join(_public_text(value or NOT_FOUND).split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _esc(value) -> str:
    return html.escape(_display_text(value))


def _public_text(value) -> str:
    text = str(value or "")
    text = re.sub(r"\s*\[(?:источник|проверено|прим\.)[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\[[^\]]*(?:источник|проверено|первоисточник)[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = text.replace(" ;", ";").replace("| |", "|")
    return " ".join(text.split())


def _display_text(value) -> str:
    text = _public_text(value).replace("₽/мес", "₽ в мес")
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


_CSS = """
:root {
  --bg: #f7f8f6;
  --card: #ffffff;
  --ink: #17231d;
  --muted: #65736c;
  --line: #dfe7e1;
  --green: #188f4f;
  --green-soft: #e5f4eb;
  --amber-soft: #fff6df;
  --red-soft: #fff0ec;
  --gray-soft: #f2f5f3;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
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
.lead { max-width: 760px; margin: 14px 0 0; color: var(--muted); font-size: 17px; }
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
.tier {
  margin-top: 28px;
  padding: 22px;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.tier-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.segment { margin: 0 0 4px; color: var(--muted); font-size: 13px; }
h2 { margin: 0; font-size: 25px; letter-spacing: 0; }
.score {
  min-width: 118px;
  border-left: 3px solid var(--green);
  padding-left: 12px;
  text-align: left;
}
.score span { display: block; color: var(--muted); font-size: 13px; }
.score b { font-size: 28px; color: var(--green); }
.panel { border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
.facts {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
  align-items: baseline;
  margin-bottom: 18px;
}
h3 { margin: 0 0 10px; font-size: 15px; }
.facts h3 { flex-basis: 100%; margin-bottom: 0; }
.facts p { margin: 0; color: var(--muted); }
.facts b { color: var(--ink); }
.block-title { margin-top: 6px; }
.cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.compare-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  background: var(--gray-soft);
}
.compare-card.sber { background: var(--green-soft); border-color: #b9ddc7; }
.compare-card.parity { background: var(--amber-soft); border-color: #eadcae; }
.compare-card.competitor { background: var(--red-soft); border-color: #edc6ba; }
.card-top span {
  display: block;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
.card-top b { display: block; margin-top: 2px; font-size: 16px; }
.compare-card p { margin: 10px 0; }
.compare-card dl {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 0;
}
.compare-card div { min-width: 0; }
.compare-card dt {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}
.compare-card dd { margin: 2px 0 0; font-size: 13px; }
.card-details {
  margin-top: 10px;
  color: var(--muted);
  font-size: 13px;
}
.card-details summary { cursor: pointer; font-weight: 700; color: var(--ink); }
.card-details p { margin: 6px 0 0; color: var(--ink); }
.table-wrap { overflow-x: auto; margin-top: 18px; }
table { width: 100%; border-collapse: collapse; min-width: 780px; }
th, td {
  border-bottom: 1px solid var(--line);
  padding: 10px 8px;
  text-align: left;
  vertical-align: top;
}
th { color: var(--muted); font-size: 12px; text-transform: uppercase; }
td:nth-child(3) { font-weight: 700; color: var(--green); white-space: nowrap; }
.raw { margin-top: 16px; color: var(--muted); }
.raw > summary { cursor: pointer; font-weight: 700; color: var(--ink); }
.raw details {
  margin-top: 8px;
  border-left: 3px solid var(--line);
  padding-left: 10px;
}
.raw p { margin: 6px 0 0; color: var(--ink); white-space: pre-wrap; }
@media (max-width: 820px) {
  h1 { font-size: 32px; }
  .tier { padding: 16px; }
  .tier-head { display: block; }
  .score { margin-top: 12px; }
  .cards { grid-template-columns: 1fr; }
  .compare-card dl { grid-template-columns: 1fr; }
}
"""
