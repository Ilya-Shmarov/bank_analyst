# -*- coding: utf-8 -*-
"""Publication gate for user-facing banking facts.

The parser may keep weak snippets for audit/provenance, but the management
HTML must only receive facts with a defensible source chain.
"""

from __future__ import annotations

from copy import deepcopy
import re

from scanner.sources import (
    NOT_FOUND,
    REFERENCE_FIELDS,
    is_authoritative_url,
    source_priority_rank,
)

PUBLISHED = "published"
BLOCKED = "blocked"
NOT_FOUND_STATUS = "not_found"


def apply_publication_gate(fields: dict) -> dict:
    """Return a copy of fields with unsafe user-facing values hidden.

    Blocked values are not discarded: the original value is kept in
    ``blocked_value`` and the reason is stored in ``publication_reason``.
    """
    gated = {}
    for field_id, field in fields.items():
        gated[field_id] = gate_field(field, field_id)
    return gated


def gate_field(field, field_id: str = ""):
    if not isinstance(field, dict):
        return field

    gated = deepcopy(field)
    value = str(gated.get("value", NOT_FOUND)).strip()
    if value.lower() == NOT_FOUND:
        gated["publication_status"] = NOT_FOUND_STATUS
        gated.setdefault("publication_reason", "Значение не найдено в доступных источниках")
        return gated

    allowed, reason = publication_decision(gated, field_id)
    if allowed:
        gated["publication_status"] = PUBLISHED
        gated["publication_reason"] = reason
        return gated

    gated["blocked_value"] = gated.get("value", NOT_FOUND)
    gated["value"] = NOT_FOUND
    gated["publication_status"] = BLOCKED
    gated["publication_reason"] = reason
    note = gated.get("note", "")
    gated["note"] = "; ".join(part for part in (note, reason) if part)
    return gated


def publication_decision(field: dict, field_id: str = "") -> tuple[bool, str]:
    """Decide whether a field may be shown in Excel/HTML."""
    if field_id == "bank_overlap":
        return True, "Справочное поле подписки, не банковское условие"

    if field.get("divergent") and field.get("source_id") != "curated":
        if _has_strong_conflict(field):
            return False, "Конфликт источников без ручного подтверждения"

    source_url = str(field.get("source_url", "")).strip()
    if not source_url:
        return False, "Нет source_url для пользовательского значения"

    raw_text = str(field.get("raw_text", "")).strip()
    if not raw_text:
        return False, "Нет raw_text/source fragment для пользовательского значения"

    source_id = field.get("source_id", "")
    quality = field.get("quality", "")

    if source_id == "curated":
        if not field.get("date_checked"):
            return False, "Ручной факт без date_checked"
        return True, "Ручной факт с source_url и датой проверки"

    if quality == "structured":
        if not field.get("tier_id") or not field.get("field_id"):
            return False, "Структурированный факт без привязки к tier_id/field_id"
        return True, "Структурированный источник с привязкой к уровню"

    if quality == "derived":
        return _derived_decision(field)

    if quality == "snippet":
        return False, "Generic keyword-snippet не публикуется в HTML без подтверждения"

    if quality == "ambiguous":
        return False, "Ambiguous/unknown значение требует ручной проверки"

    if field_id in REFERENCE_FIELDS:
        return False, "Служебное поле не публикуется без подтверждения"

    return False, f"Неподдерживаемое качество источника для публикации: {quality or 'unknown'}"


def _has_strong_conflict(field: dict) -> bool:
    """Weak or non-authoritative evidence must not block authoritative facts."""
    primary_numbers = _numbers(str(field.get("value", "")))
    if not primary_numbers:
        return False
    primary_quality = field.get("quality", "")
    primary_priority = source_priority_rank(field.get("source_id", ""))
    primary_authoritative = is_authoritative_url(field.get("source_url", ""))
    for alt in field.get("alternatives", []):
        alt_numbers = _numbers(str(alt.get("value", "")))
        if not alt_numbers or alt_numbers & primary_numbers:
            continue
        alt_authoritative = is_authoritative_url(alt.get("source_url", ""))
        if primary_authoritative and not alt_authoritative:
            continue
        alt_quality = alt.get("quality", "")
        if alt_quality == "snippet":
            continue
        alt_priority = source_priority_rank(alt.get("source_id", ""))
        if alt_quality in {"curated", "structured"}:
            return True
        if alt_priority <= primary_priority and primary_quality != "structured":
            return True
    return False


def _numbers(text: str) -> frozenset:
    nums = re.findall(r"\d+(?:[.,]\d+)?", text.replace(" ", " "))
    return frozenset(n.replace(",", ".") for n in nums)


def _derived_decision(field: dict) -> tuple[bool, str]:
    components = field.get("derived_from") or []
    if not components:
        return False, "Производное поле без трассировки derived_from"
    blocked = [
        item for item in components
        if item.get("publication_status") != PUBLISHED
    ]
    if blocked:
        names = ", ".join(item.get("field_id", "") for item in blocked if item.get("field_id"))
        return False, f"Производное поле содержит неподтверждённые компоненты: {names}"
    return True, "Производное поле собрано только из опубликованных компонентов"


def derivation_components(fields: dict, field_ids: tuple[str, ...]) -> list[dict]:
    """Compact provenance for derived fields."""
    components = []
    for field_id in field_ids:
        field = fields.get(field_id)
        if not isinstance(field, dict):
            continue
        if str(field.get("value", NOT_FOUND)).strip().lower() == NOT_FOUND:
            continue
        components.append({
            "field_id": field_id,
            "source_id": field.get("source_id", ""),
            "source_type": field.get("source_type", ""),
            "source_url": field.get("source_url", ""),
            "quality": field.get("quality", ""),
            "publication_status": field.get("publication_status", ""),
        })
    return components
