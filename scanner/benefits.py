# -*- coding: utf-8 -*-
"""Derived display model for additional premium benefits.

The scanner keeps normalized source fields such as ecosystem, auto, selectable
options and selection rules. Reports show a single user-facing "Другие
привилегии" list built from those fields without duplicating core rows.
"""

import re

from scanner.benefit_catalog import (
    benefit_id_for_title,
    canonical_title,
    classify_benefit,
    default_description,
)
from scanner.merge import field_value
from scanner.sources import NOT_FOUND

CORE_DUPLICATE_MARKERS = (
    "mir pass",
    "on·pass",
    "priority pass",
    "every lounge",
    "бизнес-залы",
    "такси",
    "ресторан",
    "кафе",
    "поездк",
)

INSURANCE_LEAK_MARKERS = (
    "страхование",
    "страховой",
    "страховая",
    "страховую",
    "страховые",
    "виза",
    "визов",
    "рейс",
    "багаж",
    "медицинские расходы",
    "горные лыжи",
    "горнолыж",
    "сноуборд",
    "несчастный случай",
    "ассистанс",
    "assistance",
    "страховая сумма",
    "срок поездки",
    "отмена поездки",
    "задержка",
)

HEALTH_OPTION_MARKERS = (
    "телемедицин",
    "анализ",
    "исследован",
    "консультац",
    "здоровье",
)

OPTION_RE = re.compile(r"опция «([^»]+)»\s*\(([^)]{1,260})\)", re.IGNORECASE)
PACKAGE_RE = re.compile(
    r"пакет\s+«([^»]+)»\s*[—-]\s*([^;|\n]{1,500})",
    re.IGNORECASE,
)
PACKAGE_PAREN_RE = re.compile(
    r"пакет\s+«([^»]+)»\s*\(([^|;\n]{1,500})\)",
    re.IGNORECASE,
)


def other_benefits_text(fields: dict) -> str:
    """Return a multiline bullet list for Excel/HTML display."""
    benefits = build_other_benefits(fields)
    if not benefits:
        return NOT_FOUND
    lines = []
    for item in benefits:
        line = f"• {item['title']}"
        if item.get("description"):
            line += f" — {item['description']}"
        if item.get("availability") == "selectable":
            line += " [опция на выбор]"
        elif item.get("availability") == "always_included" and _mixed_availability(benefits):
            line += " [включено постоянно]"
        lines.append(line)
    rule = selection_rule_summary(field_value(fields.get("selection_rules", NOT_FOUND)))
    if rule:
        lines.append(f"Условия выбора: {rule}")
    return "\n".join(lines)


def build_other_benefits(fields: dict) -> list[dict]:
    items = []
    _extend_from_text(items, field_value(fields.get("always_included_options", NOT_FOUND)),
                      "always_included")
    _extend_from_text(items, field_value(fields.get("selectable_options", NOT_FOUND)),
                      "selectable")
    _extend_from_text(items, field_value(fields.get("ecosystem", NOT_FOUND)), "unknown")
    _extend_from_text(items, field_value(fields.get("auto", NOT_FOUND)), _auto_status(fields))

    concierge = field_value(fields.get("concierge", NOT_FOUND))
    if concierge != NOT_FOUND and not _negative(concierge):
        title, description = _concierge_benefit(concierge)
        _add_item(items, title, description, "always_included", concierge)

    return _dedupe(items)


def selection_rule_summary(text: str) -> str:
    if not text or text == NOT_FOUND:
        return ""
    low = text.lower()
    if not any(marker in low for marker in ("выб", "опци", "менять", "измен", "7")):
        return ""
    blocked = ("обмен", "бонус", "менеджер", "инвест", "очеред", "запис")
    parts = []
    for part in _split_parts(text):
        part_low = part.lower()
        if any(marker in part_low for marker in blocked):
            continue
        if not any(marker in part_low for marker in ("выб", "опци", "менять", "измен", "7")):
            continue
        cleaned = _clean_sentence(part)
        if cleaned and cleaned not in parts:
            parts.append(cleaned)
    summary = "; ".join(parts[:3])
    summary = re.sub(r"раз в месяц можно выбрать одну из опций пакета",
                     "одна опция в месяц", summary, flags=re.IGNORECASE)
    summary = re.sub(r"если в текущем месяце ещё не использовались привилегии",
                     "изменить можно до использования", summary,
                     flags=re.IGNORECASE)
    summary = re.sub(r"выбранная опция действует до ближайшего 7 числа",
                     "действует до ближайшего 7-го числа", summary,
                     flags=re.IGNORECASE)
    return summary


def _extend_from_text(items: list, text: str, availability: str):
    if not text or text == NOT_FOUND or _negative(text):
        return
    matched = False
    for match in list(PACKAGE_RE.finditer(text)) + list(PACKAGE_PAREN_RE.finditer(text)):
        matched = True
        package_name = _normalize_option_title(match.group(1))
        if package_name.lower() in {"комфортное путешествие", "путешествия"}:
            continue
        title = package_name if package_name.lower() == "спорт" else f"Пакет «{package_name}»"
        description = _clean_description(match.group(2))
        item_availability = "selectable" if availability == "unknown" else availability
        _add_item(items, title, description, item_availability, match.group(0))
    for match in OPTION_RE.finditer(text):
        matched = True
        title = _normalize_option_title(match.group(1))
        description = _clean_description(match.group(2))
        item_availability = ("always_included"
                             if "всегда включ" in description.lower()
                             else availability)
        if _is_core_duplicate(title, description):
            continue
        _add_item(items, title, description, item_availability, match.group(0))
    for part in _split_parts(text):
        if (not part or OPTION_RE.search(part) or PACKAGE_RE.search(part)
                or PACKAGE_PAREN_RE.search(part)):
            continue
        title, description = _title_description(part)
        if _is_core_duplicate(title, description):
            continue
        if _looks_like_rule(part):
            continue
        if _too_generic(part):
            continue
        _add_item(items, title, description, availability, part)


def _add_item(items: list, title: str, description: str, availability: str,
              raw_text: str):
    title = _normalize_option_title(title)
    description = _clean_description(description)
    if _similar_title_description(title, description):
        description = ""
    if (not title or _too_generic(title)
            or _is_core_duplicate(title, description)
            or _is_insurance_leak(title, description)):
        return
    benefit_id = _benefit_id(title)
    if benefit_id == "sber_prime":
        availability = "always_included"
    items.append({
        "id": benefit_id,
        "title": title,
        "description": description,
        "availability": availability,
        "raw_text": raw_text,
    })


def _dedupe(items: list) -> list[dict]:
    by_id = {}
    for item in items:
        key = item["id"]
        current = by_id.get(key)
        if current is None or len(item.get("description", "")) > len(current.get("description", "")):
            by_id[key] = item
        elif current and current.get("availability") == "unknown" and item.get("availability") != "unknown":
            current["availability"] = item["availability"]
    return list(by_id.values())


def _split_parts(text: str) -> list[str]:
    public = re.sub(r"\s*\[[^\]]+\]", "", str(text))
    raw_parts = re.split(r"\s+\|\s+|;\s*|\n+|\s*•\s*", public)
    return [_clean_sentence(p) for p in raw_parts if _clean_sentence(p)]


def _title_description(part: str) -> tuple[str, str]:
    text = re.sub(r"^опция\s+", "", part, flags=re.IGNORECASE).strip(" «»")
    if " — " in text:
        title, description = text.split(" — ", 1)
        return canonical_title(title.strip(" «»")), description.strip()
    if ": " in text:
        title, description = text.split(": ", 1)
        return canonical_title(title.strip()), description.strip()
    if "(" in text and text.endswith(")"):
        title, description = text[:-1].split("(", 1)
        return canonical_title(title.strip(" «»")), description.strip()
    low = text.lower()
    if "alfa only lounge" in low:
        return "Alfa Only Лаундж", _clean_description(
            re.sub(r"alfa only\s+lounge\s*", "", text, flags=re.IGNORECASE)
        )
    if "а-клуб lounge" in low:
        return "А-Клуб Лаундж", _clean_description(
            re.sub(r"а-клуб\s+lounge\s*", "", text, flags=re.IGNORECASE)
        )
    if "alfa only" in low and "лаундж" in low:
        return "Alfa Only Лаундж", _clean_description(
            re.sub(r"alfa only\s+лаундж\s*", "", text, flags=re.IGNORECASE)
        )
    if "smart reading" in low and "саммари" in low:
        return "Саммари от Smart Reading", ""
    whole_line_markers = (
        "обмен ",
        "компенсация ",
        "3 консультации",
        "5 тыс баллов",
        "10 тыс баллов",
        "медицинское обследование",
        "учёт остатков",
        "учет остатков",
        "по тарифам платно",
        "телемедицина",
        "сбер мобайл",
        "консьерж pb service",
        "звонки ",
        "оформление бз",
        "технический лимит",
        "страхование имущества",
        "1 уровень bronze",
        "3 уровня bronze",
        "1 private",
        "2 private",
        "6 проходов",
        "юридические услуги",
        "поездки копятся",
        "кэшбэк 20%",
        "комплексный чекап",
        "медицинская программа",
        "сервис «лучи»",
        "акция «привилегии",
        "мобильная связь",
        "премиум консьерж",
        "газпром бонус",
        "до 8 бесплатных",
        "ограничено количество",
        "посещение третьяковской",
        "от 150м",
        "от 300м",
    )
    if low.startswith(whole_line_markers):
        return _clean_description(text), ""
    known_benefit = classify_benefit(text)
    if known_benefit:
        description = default_description(known_benefit.benefit_id)
        cleaned = _clean_description(
            text.replace(known_benefit.title, "", 1).strip(" ,—-")
        )
        return known_benefit.title, cleaned or description
    words = text.split()
    return " ".join(words[:4]).strip(" ,—-"), " ".join(words[4:]).strip(" ,—-")


def _normalize_option_title(title: str) -> str:
    cleaned = title.strip()
    if cleaned.startswith("«") and cleaned.endswith("»"):
        cleaned = cleaned[1:-1].strip()
    mapping = {
        "авто": "Авто",
        "самокат": "Самокат",
        "питомцы": "Питомцы",
        "здоровье": "Здоровье",
        "спорт и красота": "Спорт и красота",
        "комфортное путешествие": "Комфортное путешествие",
        "спорт": "Спорт",
        "развлечения": "Развлечения",
    }
    normalized = mapping.get(cleaned.lower(), cleaned[:1].upper() + cleaned[1:])
    return canonical_title(normalized)


def _clean_description(text: str) -> str:
    cleaned = _clean_sentence(text)
    cleaned = re.sub(r"\s*\(всегда включен[ао]\)\s*", "", cleaned,
                     flags=re.IGNORECASE)
    cleaned = cleaned.replace("кешбэк", "кэшбэк")
    return cleaned.strip(" ,;—-")


def _clean_sentence(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text).replace("•", "").strip()).strip(" |;")
    value = re.sub(r"«\s+", "«", value)
    value = re.sub(r"\s+»", "»", value)
    return value


def _benefit_id(title: str) -> str:
    catalog_match = classify_benefit(title)
    if catalog_match:
        return catalog_match.benefit_id
    low = title.lower().replace("ё", "е")
    aliases = {
        "консьерж aspire": "консьерж",
        "aspire": "консьерж",
        "консьерж": "консьерж",
        "автоуслуги": "auto",
        "авто": "auto",
    }
    for marker, value in aliases.items():
        if marker in low:
            return value
    return benefit_id_for_title(title)


def _is_core_duplicate(title: str, description: str) -> bool:
    low = f"{title} {description}".lower()
    if title.strip().lower().startswith("пакет «"):
        return False
    if title.strip().lower() in {"консьерж", "aspire"}:
        return True
    if "бизнес-зал сбер" in low or "alfa only lounge" in low:
        return False
    return any(marker in low for marker in CORE_DUPLICATE_MARKERS)


def _similar_title_description(title: str, description: str) -> bool:
    title_norm = re.sub(r"[^a-zа-я0-9]+", " ", title.lower().replace("ё", "е")).strip()
    desc_norm = re.sub(r"[^a-zа-я0-9]+", " ", description.lower().replace("ё", "е")).strip()
    title_norm = re.sub(r"\bи\b", " ", title_norm)
    desc_norm = re.sub(r"\bи\b", " ", desc_norm)
    title_norm = re.sub(r"\s+", " ", title_norm).strip()
    desc_norm = re.sub(r"\s+", " ", desc_norm).strip()
    if title_norm == "спорт":
        return False
    if not title_norm or not desc_norm:
        return False
    if title_norm == desc_norm:
        return True
    return title_norm in desc_norm or desc_norm in title_norm


def _is_insurance_leak(title: str, description: str) -> bool:
    low = f"{title} {description}".lower().replace("ё", "е")
    if title.strip().lower().startswith("пакет «"):
        return False
    if "доктис" in low or "телемедицин" in low:
        return False
    if "страхование имущества" in low:
        return False
    if title.strip().lower().replace("ё", "е") == "здоровье":
        return not any(marker in low for marker in HEALTH_OPTION_MARKERS)
    return any(marker in low for marker in INSURANCE_LEAK_MARKERS)


def _negative(text: str) -> bool:
    low = text.strip().lower()
    return low.startswith(("—", "-", "нет —", "нет,"))


def _too_generic(text: str) -> bool:
    low = text.lower()
    short_allowed = {"авто", "рбк", "okko"}
    return ((len(text) < 5 and low not in short_allowed)
            or low in {"включено", "на выбор"}
            or low.startswith("включено исследование")
            or low.startswith("исследование до")
            or low.startswith(("в вопросе #", "подробнее")))


def _looks_like_rule(text: str) -> bool:
    low = text.lower()
    return ("можно выбрать" in low or "можно сменить" in low
            or "выбранная опция" in low)


def _auto_status(fields: dict) -> str:
    auto = field_value(fields.get("auto", NOT_FOUND)).lower()
    if "всегда включ" in auto:
        return "always_included"
    if "опция" in auto:
        return "selectable"
    return "unknown"


def _clean_title_text(text: str) -> str:
    text = re.sub(r"^есть\s+[—-]\s*", "", text, flags=re.IGNORECASE)
    return _clean_description(text)


def _concierge_benefit(text: str) -> tuple[str, str]:
    low = text.lower()
    if "only assist" in low:
        return "Only Assist", "Консьерж-сервис"
    if "prime" in low:
        return "PRIME", "Консьерж-сервис"
    if "pb service" in low:
        return "Консьерж Pb Service", ""
    if "aspire" in low:
        return "Консьерж Aspire", ""
    return "Консьерж", _clean_title_text(text)


def _mixed_availability(items: list[dict]) -> bool:
    statuses = {i.get("availability") for i in items if i.get("availability") != "unknown"}
    return len(statuses) > 1
