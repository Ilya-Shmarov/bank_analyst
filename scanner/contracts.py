# -*- coding: utf-8 -*-
"""Post-merge quality contracts for scanned premium banking data.

Contracts do not create or override facts. They only inspect already selected
fields and report suspicious results before Excel/HTML publication.
"""

from __future__ import annotations

from scanner.formatting import normalize_source_text, validate_user_visible_text
from scanner.merge import field_value
from scanner.sources import NOT_FOUND, REFERENCE_FIELDS


BANK_REQUIRED_FIELDS = (
    "entry_conditions",
    "lounge_access",
    "insurance",
    "concierge",
    "other_benefits",
)


FIELD_MARKERS = {
    "vtb_privilege_2": {
        "entry_conditions": ("2.5 млн ₽", "2 млн ₽ регионы"),
        "selection_rules": ("Преференции", "2 в мес"),
        "lounge_access": ("2", "24 в год"),
        "restaurants": ("2", "12 в год", "2500 ₽"),
        "taxi": ("2", "12 в год", "1000 ₽"),
        "other_benefits": ("Помощь на дорогах", "АМА консьерж", "appoint", "ON·PACK"),
    },
    "vtb_privilege_3": {
        "entry_conditions": ("6 млн ₽",),
        "selection_rules": ("Преференции", "6 в мес"),
        "lounge_access": ("6", "48 в год"),
        "restaurants": ("6", "24 в год", "2500 ₽"),
        "taxi": ("6", "24 в год", "1000 ₽"),
        "other_benefits": ("Помощь на дорогах", "АМА консьерж", "5 тыс баллов", "ON·PACK"),
    },
    "vtb_privilege_4": {
        "entry_conditions": ("10 млн ₽",),
        "selection_rules": ("Преференции", "10 в мес"),
        "lounge_access": ("10", "60 в год"),
        "restaurants": ("10", "30 в год", "2500 ₽"),
        "taxi": ("10", "30 в год", "1000 ₽"),
        "other_benefits": ("Помощь на дорогах", "АМА консьерж", "5 тыс баллов", "Телемедицина", "ON·PACK"),
    },
    "vtb_prime_5": {
        "entry_conditions": ("16667 ₽ в мес",),
        "selection_rules": ("Преференции", "10 в мес"),
        "lounge_access": ("10", "60 в год"),
        "restaurants": ("10", "30 в год", "2500 ₽"),
        "taxi": ("-",),
        "other_benefits": ("Помощь на дорогах", "АМА консьерж", "appoint", "Фитмост", "ON·PACK"),
    },
    "vtb_prime_6": {
        "entry_conditions": ("15 млн ₽",),
        "selection_rules": ("Преференции", "15 в мес"),
        "lounge_access": ("безлимит",),
        "restaurants": ("15", "40 в год", "2500 ₽"),
        "taxi": ("-",),
        "other_benefits": ("Помощь на дорогах", "АМА консьерж", "Телемедицина", "Доктис", "Фитмост", "10 тыс баллов"),
    },
    "vtb_prime_7": {
        "entry_conditions": ("50 млн ₽", "30 млн ₽ регионы"),
        "selection_rules": ("Преференции", "20 в мес"),
        "lounge_access": ("безлимит",),
        "restaurants": ("20", "50 в год", "2500 ₽"),
        "taxi": ("-",),
        "other_benefits": ("Помощь на дорогах", "АМА консьерж", "Телемедицина", "Доктис", "Фитмост", "10 тыс баллов"),
    },
    "vtb_prime_8": {
        "entry_conditions": ("100 млн ₽", "50 млн ₽ регионы"),
        "selection_rules": ("Преференции", "25 в мес"),
        "lounge_access": ("безлимит",),
        "restaurants": ("25", "50 в год", "2500 ₽"),
        "taxi": ("-",),
        "other_benefits": ("Помощь на дорогах", "АМА консьерж", "Телемедицина", "Доктис", "Медицинское обследование", "10 тыс баллов"),
    },
    "sber_first_4": {
        "other_benefits": ("СберПрайм", "Okko", "Бизнес-зал Сбер", "Компенсация БЗ"),
    },
    "sber_first_5": {
        "other_benefits": ("СберПрайм", "Okko", "Бизнес-зал Сбер", "Компенсация БЗ"),
    },
    "sber_private_6": {
        "other_benefits": ("СберПрайм", "Okko", "СберПраво", "Сбер Мобайл", "Pb Service"),
    },
    "alfa_only_1": {
        "other_benefits": ("SimplePrivé", "Only Assist"),
    },
    "alfa_only_2": {
        "other_benefits": ("Консультации", "Альфа-Мобайл", "Smart Reading", "Only Assist", "Alfa Only Лаундж", "SimplePrivé"),
    },
    "alfa_only_3": {
        "other_benefits": ("Консультации", "Альфа-Мобайл", "Smart Reading", "РБК", "Only Assist", "Alfa Only Лаундж", "SimplePrivé"),
    },
    "alfa_only_4": {
        "other_benefits": ("Консультации", "Альфа-Мобайл", "Smart Reading", "РБК", "Only Assist", "Alfa Only Лаундж", "SimplePrivé"),
    },
    "alfa_aclub": {
        "other_benefits": ("Альфа-Мобайл", "PRIME", "Alfa Only Лаундж", "А-Клуб Лаундж", "SimplePrivé", "Медицинский консьерж"),
    },
}


def validate_scan_contracts(results: dict) -> list[dict]:
    issues = []
    for tier_id, entry in results.items():
        fields = entry.get("fields", {})
        bank = entry.get("bank", "")
        tier = entry.get("tier", tier_id)
        for field_id, field in fields.items():
            value = field_value(field)
            if isinstance(field, dict) and field.get("publication_status") == "blocked":
                issues.append(_issue(
                    "warning", "publication_blocked", bank, tier, tier_id, field_id,
                    field.get("publication_reason", "Значение заблокировано для HTML"),
                    field.get("blocked_value", value),
                ))
            if value == NOT_FOUND:
                continue
            if field_id not in REFERENCE_FIELDS:
                issues.extend(_text_issues(bank, tier, tier_id, field_id, value))
            if field_id not in REFERENCE_FIELDS:
                issues.extend(_provenance_issues(bank, tier, tier_id, field_id, field))
        issues.extend(_required_field_issues(entry, tier_id))
        issues.extend(_marker_issues(entry, tier_id))
    return issues


def _text_issues(bank: str, tier: str, tier_id: str, field_id: str, value: str) -> list[dict]:
    if str(value).strip() in {"-", "—"}:
        return []
    issues = []
    raw_problems = validate_user_visible_text(str(value))
    problems = [
        problem for problem in raw_problems
        if problem in {"contains replacement character", "looks like binary or corrupted text"}
    ]
    problems += [
        problem for problem in validate_user_visible_text(normalize_source_text(str(value)))
        if problem not in problems
    ]
    for problem in problems:
        severity = "error" if problem in {
            "contains replacement character",
            "looks like binary or corrupted text",
        } else "warning"
        issues.append(_issue(severity, "text_quality", bank, tier, tier_id, field_id, problem, value))
    if "в — год" in str(value):
        issues.append(_issue("error", "broken_phrase", bank, tier, tier_id, field_id,
                             "Сломана цельная фраза 'в год'", value))
    return issues


def _provenance_issues(bank: str, tier: str, tier_id: str, field_id: str, field) -> list[dict]:
    if not isinstance(field, dict):
        return [_issue("error", "provenance", bank, tier, tier_id, field_id,
                       "Поле не содержит provenance-структуру", field)]
    if field.get("source_id") == "derived":
        return []
    issues = []
    if not field.get("source_url"):
        issues.append(_issue("error", "provenance", bank, tier, tier_id, field_id,
                             "Нет source_url у найденного значения", field.get("value", "")))
    if not field.get("raw_text"):
        issues.append(_issue("warning", "provenance", bank, tier, tier_id, field_id,
                             "Нет raw_text у найденного значения", field.get("value", "")))
    if field.get("conflict_status") == "unknown":
        issues.append(_issue("warning", "ambiguous", bank, tier, tier_id, field_id,
                             "Значение помечено как ambiguous/unknown", field.get("value", "")))
    return issues


def _required_field_issues(entry: dict, tier_id: str) -> list[dict]:
    if not tier_id.startswith(("sber_", "alfa_", "vtb_", "tbank_", "gpb_", "ozonbank_", "raif_")):
        return []
    fields = entry.get("fields", {})
    issues = []
    for field_id in BANK_REQUIRED_FIELDS:
        if field_value(fields.get(field_id)) == NOT_FOUND:
            issues.append(_issue("warning", "required_field", entry.get("bank", ""),
                                 entry.get("tier", tier_id), tier_id, field_id,
                                 "Ключевое поле не найдено", NOT_FOUND))
    return issues


def _marker_issues(entry: dict, tier_id: str) -> list[dict]:
    contracts = FIELD_MARKERS.get(tier_id, {})
    fields = entry.get("fields", {})
    issues = []
    for field_id, markers in contracts.items():
        value = str(field_value(fields.get(field_id)))
        low = value.lower()
        for marker in markers:
            if marker.lower() not in low:
                issues.append(_issue("error", "field_marker", entry.get("bank", ""),
                                     entry.get("tier", tier_id), tier_id, field_id,
                                     f"Не найден обязательный маркер: {marker}", value))
    return issues


def _issue(severity: str, code: str, bank: str, tier: str, tier_id: str,
           field_id: str, message: str, value) -> dict:
    return {
        "severity": severity,
        "code": code,
        "bank": bank,
        "tier": tier,
        "tier_id": tier_id,
        "field_id": field_id,
        "message": message,
        "value": str(value)[:500],
    }
