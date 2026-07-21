# -*- coding: utf-8 -*-
"""User-facing text formatting for Excel and HTML output.

This module formats already collected facts for display only. It must not
change source priority, scoring, parsed values, or provenance.
"""

import re

from scanner.sources import NOT_FOUND

STOP_WORDS = {
    "и", "или", "либо", "а", "но", "в", "во", "на", "по", "к", "ко",
    "с", "со", "у", "о", "об", "от", "до", "для", "за", "из", "при",
    "как", "что", "если", "то", "не", "без",
}

SERVICE_NAME_CASE = {
    "soft travel": "Soft Travel",
    "only assist": "Only Assist",
    "phoenix pass": "Phoenix Pass",
    "mir pass": "Mir Pass",
    "smart reading": "Smart Reading",
}

BAD_TERMINALS = ("-", "/", "|", "(", ",", ":")
NULL_TOKEN_RE = re.compile(r"\b(?:null|none|nan)\b", re.IGNORECASE)
TRUNCATED_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+(?:\.\.\.|…)")


def normalize_source_text(text: str) -> str:
    """Return readable text for user-visible cells and HTML."""
    if text is None:
        return ""
    value = str(text).replace("\xa0", " ")
    if _looks_like_binary(value):
        return NOT_FOUND
    if value.strip() in {"-", "—"}:
        return "—"
    value = value.replace("₽/мес", "₽ в мес")
    value = re.sub(r"\s*\[(?:источник|проверено|прим\.)[^\]]*\]", "", value,
                   flags=re.IGNORECASE)
    value = re.sub(r"\s*\[[^\]]*(?:источник|проверено|первоисточник)[^\]]*\]",
                   "", value, flags=re.IGNORECASE)
    value = _remove_question_references(value)
    value = _normalize_access_text(value)
    value = _replace_pipe_lists(value)
    value = cleanup_punctuation(value)
    value = _normalize_known_phrases(value)
    value = _normalize_sber_tariff_names(value)
    return cleanup_punctuation(value)


def normalize_user_text(text: str) -> str:
    """Public alias for all user-visible text normalization."""
    return normalize_source_text(text)


def _normalize_sber_tariff_names(text: str) -> str:
    """Sber no longer uses the public "Новый ..." tariff naming in reports."""
    value = str(text or "")
    value = re.sub(r"\bНовый\s+(?=СберПремьер|СберПервый|Sber Private)",
                   "", value)
    return value


def _remove_question_references(text: str) -> str:
    """Drop PBI FAQ anchors from user-visible benefit descriptions."""
    value = str(text or "")
    had_trailing_details = bool(re.search(
        r"подробнее\s*(?:[;,.]\s*)*$",
        value,
        flags=re.IGNORECASE,
    ))
    value = re.sub(
        r"\s*[,;]?\s*подробнее\s*[,;]?\s*в\s+вопросе\s*#\s*\d+\s*\.?",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\s*[,;]?\s*в\s+вопросе\s*#\s*\d+\s*\.?",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\s*[,;]?\s*подробнее\s*(?:[;,.]\s*)*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    if had_trailing_details:
        stripped = value.rstrip(" ,;")
        if stripped and stripped[-1] not in ".!?":
            value = stripped + "."
    return value


def normalize_list_separators(text: str) -> str:
    """Normalize technical list separators without changing facts."""
    return _replace_pipe_lists(str(text or ""))


def format_list(items: list[str]) -> str:
    """Format a short Russian list with commas and final 'и'."""
    cleaned = [_normalize_service_name(cleanup_punctuation(i)) for i in items if cleanup_punctuation(i)]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return " и ".join(cleaned)
    separator = "; " if any("," in item or len(item) > 45 for item in cleaned) else ", "
    return separator.join(cleaned[:-1]) + " и " + cleaned[-1]


def _looks_like_binary(text: str) -> bool:
    value = str(text or "")
    if "�" in value:
        return True
    if sum(1 for ch in value if ch in "ÐÑ") >= 3:
        return True
    if len(value) < 30:
        return False
    readable = sum(
        1 for ch in value
        if ch.isalnum() or ch.isspace()
        or ch in ".,;:!?%₽$€№«»()—–-+/=><≥≤→≈×"
    )
    return readable / max(len(value), 1) < 0.75


def format_natural_list(items: list[str]) -> str:
    """Public alias for natural Russian list formatting."""
    return format_list(items)


def make_complete_summary(text: str, max_length: int = 240) -> str:
    """Shorten text without cutting a word or unfinished phrase."""
    value = normalize_source_text(text)
    if len(value) <= max_length:
        return value
    parts = _logical_parts(value)
    summary_parts = []
    for part in parts:
        candidate = " ".join([*summary_parts, part]).strip()
        if len(candidate) <= max_length:
            summary_parts.append(part)
            continue
        break
    if summary_parts:
        return _ensure_complete_end(" ".join(summary_parts))
    fallback = _safe_cut(value, max_length)
    return _ensure_complete_end(fallback)


def split_summary_and_details(text: str, max_length: int = 240) -> dict:
    """Return {"summary", "details"} while preserving the full normalized text."""
    details = normalize_source_text(text)
    summary = make_complete_summary(details, max_length)
    return {
        "summary": summary,
        "details": details if details and details != summary else "",
    }


def validate_user_visible_text(text: str) -> list[str]:
    """Return a list of user-visible text quality problems."""
    value = str(text if text is not None else "")
    problems = []
    if "�" in value:
        problems.append("contains replacement character")
    if _looks_like_binary(value):
        problems.append("looks like binary or corrupted text")
    if "|" in value:
        problems.append("contains pipe separator")
    if TRUNCATED_WORD_RE.search(value):
        problems.append("contains word cut with ellipsis")
    if NULL_TOKEN_RE.search(value):
        problems.append("contains null/None/NaN token")
    if "  " in value:
        problems.append("contains double spaces")
    if ", ," in value or re.search(r",\s*,", value):
        problems.append("contains repeated comma")
    if "( , )" in value or re.search(r"\(\s*,\s*\)", value):
        problems.append("contains empty technical parentheses")
    stripped = value.rstrip()
    is_url = stripped.startswith(("http://", "https://"))
    if not is_url and stripped.endswith(BAD_TERMINALS):
        problems.append("ends with invalid terminal character")
    if value.count("(") != value.count(")"):
        problems.append("has unbalanced parentheses")
    if re.search(r"([,;:!?])\1+", value) or "..." in value:
        problems.append("contains repeated punctuation")
    return problems


def assert_user_visible_text(text: str, context: str = "") -> str:
    """Raise ValueError if a formatted user-facing string is invalid."""
    problems = validate_user_visible_text(text)
    if problems:
        prefix = f"{context}: " if context else ""
        raise ValueError(prefix + "; ".join(problems) + f" -> {text[:240]}")
    return text


def cleanup_punctuation(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    value = re.sub(r"\.{2,}", ".", value)
    value = re.sub(r"(?<=\d),\s+(?=\d{3}\b)", ",", value)
    value = value.replace(" ,", ",").replace(" ;", ";").replace(" .", ".")
    value = re.sub(r",\s*,+", ",", value)
    value = re.sub(r"[;,]\s*\.", ".", value)
    value = re.sub(r";\s*;+", ";", value)
    value = re.sub(r"\.;(?=\s*\S)", ";", value)
    value = re.sub(r"\.;\s*$", ".", value)
    value = re.sub(r"\(\s*,\s*\)", "", value)
    value = re.sub(r"\(\s*\)", "", value)
    value = _balance_parentheses(value)
    value = re.sub(r"\s+([,.;:])", r"\1", value)
    value = re.sub(r"«\s+", "«", value)
    value = re.sub(r"\s+»", "»", value)
    value = re.sub(r",(?=\S)(?!\d)", ", ", value)
    value = re.sub(r"([;:])(?=\S)", r"\1 ", value)
    value = re.sub(r"\s{2,}", " ", value)
    value = value.replace(" + ", " и ")
    value = re.sub(r"(?:;\s*)?[-—]\s*$", "", value)
    return value.strip(" ,;")


def _balance_parentheses(text: str) -> str:
    value = str(text)
    open_count = value.count("(")
    close_count = value.count(")")
    if open_count > close_count:
        for _ in range(open_count - close_count):
            idx = value.rfind("(")
            if idx >= 0:
                value = value[:idx] + value[idx + 1:]
    elif close_count > open_count:
        for _ in range(close_count - open_count):
            idx = value.find(")")
            if idx >= 0:
                value = value[:idx] + value[idx + 1:]
    return value


def _normalize_access_text(text: str) -> str:
    access_match = re.search(r"доступ через\s+(.+)", text, flags=re.IGNORECASE | re.S)
    if not access_match:
        return text
    prefix = text[:access_match.start()].strip(" ,;")
    raw_list = access_match.group(1)
    if "|" not in raw_list and re.search(r"\sи\s", raw_list):
        return text
    items = _items_from_technical_list(raw_list)
    if not items:
        return text
    access = "Доступ через " + format_list(items) + "."
    if prefix:
        prefix = _normalize_visit_counts(prefix)
        return prefix.rstrip(".") + ". " + access
    return access


def _replace_pipe_lists(text: str) -> str:
    if "|" not in text:
        return text
    pipe_parts = [cleanup_punctuation(p) for p in re.split(r"\s*\|\s*", text)
                  if cleanup_punctuation(p)]
    looks_like_short_list = (
        2 <= len(pipe_parts) <= 8
        and all(len(part) <= 45 for part in pipe_parts)
        and not any("•" in part or re.search(r"\d+,\d", part) for part in pipe_parts)
    )
    if looks_like_short_list:
        parts = [
            _normalize_service_name(part)
            for part in pipe_parts
            if part not in {"(", ")"}
        ]
        return format_list(parts)
    return cleanup_punctuation(re.sub(r"\s*\|\s*", "; ", text))


def _items_from_technical_list(text: str) -> list[str]:
    value = str(text)
    value = value.replace("·ON·PASS", "ON·PASS")
    value = value.replace("·ON·PASS Premium", "ON·PASS Premium")
    value = re.sub(r"[()]", " ", value)
    chunks = re.split(r"\s*\|\s*|\s*,\s*|\s*;\s*", value)
    items = []
    seen = set()
    for chunk in chunks:
        item = cleanup_punctuation(chunk)
        item = re.sub(r"^(?:и|или)\s+", "", item, flags=re.IGNORECASE)
        if not item or item in {"(", ")"} or item.lower() in {"доступ через", "подробнее"}:
            continue
        if item.lower().startswith(("в вопросе", "подробнее")):
            continue
        item = _normalize_service_name(item)
        key = item.lower()
        if key not in seen:
            seen.add(key)
            items.append(item)
    return items


def _normalize_known_phrases(text: str) -> str:
    value = _normalize_visit_counts(text)
    value = re.sub(r"\b(\d+)\s+в\s+мес\b", r"\1 в месяц", value,
                   flags=re.IGNORECASE)
    value = re.sub(r"(?<!до )\b(\d+)\s+в\s+год\b", r"до \1 в год", value,
                   flags=re.IGNORECASE)
    return value


def _normalize_visit_counts(text: str) -> str:
    value = re.sub(r"\b(\d+)\s+в\s+мес\b",
                   lambda m: f"{m.group(1)} {_plural(int(m.group(1)), 'посещение', 'посещения', 'посещений')} в месяц",
                   text, flags=re.IGNORECASE)
    value = re.sub(r"\((\d+)\s+в\s+год\)",
                   lambda m: f", до {m.group(1)} в год",
                   value, flags=re.IGNORECASE)
    return value


def _normalize_service_name(item: str) -> str:
    low = item.lower()
    if low in SERVICE_NAME_CASE:
        return SERVICE_NAME_CASE[low]
    if low.startswith("on·pass"):
        return item.replace("·ON·PASS", "ON·PASS").replace("·on·pass", "ON·PASS")
    return item[:1].upper() + item[1:] if item.islower() else item


def _logical_parts(text: str) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+|;\s+|\n+", text)
    parts = []
    for part in raw:
        cleaned = cleanup_punctuation(part)
        if not cleaned:
            continue
        if not re.search(r"[.!?]$", cleaned):
            cleaned += ";"
        parts.append(cleaned)
    return parts


def _safe_cut(text: str, max_length: int) -> str:
    boundary = -1
    for pattern in (r"[.!?;]\s", r",\s", r"\s"):
        matches = list(re.finditer(pattern, text[:max_length]))
        if matches:
            boundary = matches[-1].start()
            break
    if boundary <= 0:
        boundary = max_length
    return text[:boundary].rstrip(" ,;:")


def _ensure_complete_end(text: str) -> str:
    value = cleanup_punctuation(text).rstrip(" …")
    while value.split() and value.split()[-1].lower().strip(".,;:!?") in STOP_WORDS:
        value = " ".join(value.split()[:-1]).rstrip(" ,;:")
    if not value:
        return NOT_FOUND
    if value.endswith(("...", "…")):
        value = value.rstrip(".…").rstrip()
    value = value.rstrip("-/|(:;, ")
    if not re.search(r"[.!?;]$", value):
        value += "."
    return value


def _plural(count: int, one: str, few: str, many: str) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return one
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return few
    return many
