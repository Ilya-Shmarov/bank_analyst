# -*- coding: utf-8 -*-
"""
Слияние данных одного тира из нескольких источников.

Правила (описаны также на листе «Методика оценки» отчёта):
  1. curated (верифицированный вручную факт с ссылкой на первоисточник) —
     всегда приоритетнее автоматического парсинга.
  2. Среди автоматических источников сначала сравнивается КАЧЕСТВО данных:
     structured (структурированный парсер, например dt/dd на ПБИ) выигрывает
     у snippet (цитаты по ключевым словам). Внутри одного качества — приоритет
     источника из SOURCE_META (официальный сайт банка первый).
  3. Значения остальных источников не выбрасываются: они сохраняются в
     alternatives. Если их числовое содержание расходится с основным
     значением — поле помечается divergent=True с комментарием.

Формат объединённого поля:
{
  "value": str, "source_id": str, "source_name": str, "source_url": str,
  "date_checked": "YYYY-MM-DD", "quality": "curated|structured|snippet",
  "divergent": bool, "alternatives": [{"source_name", "value"}], "note": str,
}
"""

import re
from datetime import date, datetime

from scanner.curated import STALE_DAYS
from scanner.sources import NOT_FOUND, SOURCE_META

QUALITY_RANK = {"curated": 0, "structured": 1, "snippet": 2}


def _numbers(text: str) -> frozenset:
    """Числовая сигнатура значения для сравнения источников между собой."""
    nums = re.findall(r"\d+(?:[.,]\d+)?", text.replace(" ", " "))
    return frozenset(n.replace(",", ".") for n in nums)


def _source_priority(source_id: str) -> int:
    return SOURCE_META.get(source_id, {"priority": 99})["priority"]


def merge_tier_fields(parsed_sources: list, curated: dict, field_ids: list,
                      scan_date: str) -> dict:
    """
    parsed_sources: [{"source_id", "url", "quality", "fields": {fid: value}}]
    curated: {fid: {"value", "source_url", "date_checked", "note"}}
    Возвращает {fid: merged_field}.
    """
    merged = {}
    for fid in field_ids:
        candidates = []
        if fid in curated:
            fact = curated[fid]
            candidates.append({
                "value": fact["value"],
                "source_id": "curated",
                "source_url": fact["source_url"],
                "date_checked": fact["date_checked"],
                "quality": "curated",
                "note": fact.get("note", ""),
            })
        for src in parsed_sources:
            value = src["fields"].get(fid, NOT_FOUND)
            if value == NOT_FOUND:
                continue
            candidates.append({
                "value": value,
                "source_id": src["source_id"],
                "source_url": src["url"],
                "date_checked": scan_date[:10],
                "quality": src["quality"],
                "note": "",
            })

        if not candidates:
            merged[fid] = _empty_field(scan_date)
            continue

        candidates.sort(key=lambda c: (QUALITY_RANK[c["quality"]],
                                       _source_priority(c["source_id"])))
        primary, rest = candidates[0], candidates[1:]
        merged[fid] = _build_field(primary, rest)
    return merged


def _build_field(primary: dict, rest: list) -> dict:
    alternatives = []
    divergent = False
    notes = [primary["note"]] if primary["note"] else []

    primary_nums = _numbers(primary["value"])
    for cand in rest:
        alternatives.append({
            "source_name": SOURCE_META.get(cand["source_id"], {}).get(
                "name", cand["source_id"]),
            "value": cand["value"],
        })
        cand_nums = _numbers(cand["value"])
        # Расхождение фиксируем только по числам: разные формулировки без
        # чисел — это нормально, разные цифры — сигнал для ручной сверки
        if primary_nums and cand_nums and not (cand_nums & primary_nums):
            divergent = True
            src_name = SOURCE_META.get(cand["source_id"], {}).get(
                "name", cand["source_id"])
            notes.append(f"числа расходятся с {src_name}")

    if primary["source_id"] == "curated" and _is_stale(primary["date_checked"]):
        notes.append(f"проверено {primary['date_checked']} — "
                     f"старше {STALE_DAYS} дн, проверить актуальность")

    return {
        "value": primary["value"],
        "source_id": primary["source_id"],
        "source_name": SOURCE_META.get(primary["source_id"], {}).get(
            "name", primary["source_id"]),
        "source_url": primary["source_url"],
        "date_checked": primary["date_checked"],
        "quality": primary["quality"],
        "divergent": divergent,
        "alternatives": alternatives,
        "note": "; ".join(notes),
    }


def _empty_field(scan_date: str) -> dict:
    return {
        "value": NOT_FOUND,
        "source_id": "",
        "source_name": "",
        "source_url": "",
        "date_checked": scan_date[:10],
        "quality": "",
        "divergent": False,
        "alternatives": [],
        "note": "",
    }


def _is_stale(date_checked: str) -> bool:
    try:
        checked = datetime.strptime(date_checked, "%Y-%m-%d").date()
    except ValueError:
        return False
    return (date.today() - checked).days > STALE_DAYS


def field_value(field) -> str:
    """Значение поля независимо от формата (старый str / новый dict)."""
    if isinstance(field, dict):
        return field.get("value", NOT_FOUND)
    return field if field is not None else NOT_FOUND
