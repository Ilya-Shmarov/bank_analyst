# -*- coding: utf-8 -*-
"""
История сканов и diff между последним и предыдущим.

history.json:
{
  "scans": [
    {
      "date": "2026-07-02T12:00:00",
      "results": { "<tier_id>": {"bank": ..., "tier": ..., "fields": {...},
                                  "source_url": ..., "status": ...} },
      "meta": { "sources_ok": [...], "sources_failed": {...} }
    },
    ...
  ],
  "changelog": [ {"scan_date": ..., "prev_date": ..., "bank": ..., "tier": ...,
                   "field": ..., "old": ..., "new": ...}, ... ]
}
"""

import json
import re
from pathlib import Path

from scanner.merge import field_value
from scanner.sources import NOT_FOUND, REFERENCE_FIELDS

MAX_SCANS_KEPT = 20
MAX_SERVICE_LOG = 5000


def _normalize(text: str) -> str:
    return re.sub(r"[\s.,;:|«»\"'()\-–—]+", " ", (text or "").lower()).strip()


def _nums(text: str) -> frozenset:
    return frozenset(_semantic_numbers(text))


_NUMBER_RE = re.compile(r"\d+(?:[\s\u00a0]\d{3})*(?:[.,]\d+)?")
_EXPLANATORY_PAREN_RE = re.compile(r"\(([^()]*)\)")
_CATEGORY_PREFIX_RE = re.compile(
    r"^\s*(?:"
    r"бизнес[-\s]?залы?|такси|транспорт|консьерж(?:[-\s]?сервис)?|"
    r"кэшбэк|cashback|вклады?|накопительные счета?|рестораны?|"
    r"страхование|условия входа|стоимость обслуживания"
    r")\s*[-—:]\s*",
    re.IGNORECASE,
)
_EXPLANATORY_MARKERS = (
    "ранее", "порог после", "порог до", "после 2024", "до 2024",
    "истор", "справоч", "входит в", "основные привилегии",
    "бессрочно", "части сервисов",
)
_ABSENT_MARKERS = (
    "не найдено", "нет", "не предостав", "отсутств", "недоступ",
    "не предусмотр",
)
_BRAND_ALIASES = {
    "prime": ("prime", "прайм"),
    "aspire": ("aspire", "аспайр"),
    "priority pass": ("priority pass", "prioritypass"),
    "onpass": ("onpass", "онпасс"),
    "mir pass": ("mir pass", "mirpass", "мир pass"),
    "mondial": ("mondial", "мондиаль"),
    "class assistance": ("class assistance",),
    "best doctor": ("best doctor", "bestdoctor"),
    "fitmost": ("fitmost",),
    "okko": ("okko", "окко"),
    "sberprime": ("sberprime", "сберпрайм"),
}


def _strip_explanatory_parentheses(text: str) -> str:
    def replace(match):
        body = match.group(1).lower()
        if any(marker in body for marker in _EXPLANATORY_MARKERS):
            return " "
        return match.group(0)

    return _EXPLANATORY_PAREN_RE.sub(replace, text or "")


def _semantic_numbers(text: str) -> tuple[str, ...]:
    cleaned = _strip_explanatory_parentheses(text)
    numbers = []
    for match in _NUMBER_RE.findall(cleaned):
        value = re.sub(r"[\s\u00a0]", "", match).replace(",", ".")
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        value = value.lstrip("0") or "0"
        numbers.append(value)
    return tuple(numbers)


def _canonical_condition_text(text: str) -> str:
    cleaned = _strip_explanatory_parentheses(text).lower()
    cleaned = cleaned.replace("ё", "е")
    cleaned = re.sub(r"\bбизнес\s+залы\b", "бизнес-залы", cleaned)
    cleaned = _CATEGORY_PREFIX_RE.sub("", cleaned)
    cleaned = re.sub(r"[\s.,;:|«»\"'()\-–—/]+", " ", cleaned)
    cleaned = re.sub(r"\b(?:есть|доступен|доступно|сервис)\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _availability_state(text: str) -> str:
    normalized = _normalize(text)
    if any(marker in normalized for marker in _ABSENT_MARKERS):
        if "без огранич" not in normalized:
            return "absent"
    return "present"


def _is_unlimited(text: str) -> bool:
    normalized = _normalize(text)
    return "безлимит" in normalized or "неогранич" in normalized


def _brand_tokens(text: str) -> tuple[str, ...]:
    normalized = _canonical_condition_text(text)
    found = []
    for brand, aliases in _BRAND_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            found.append(brand)
    return tuple(found)


def _condition_signature(text: str) -> dict:
    return {
        "numbers": _semantic_numbers(text),
        "availability": _availability_state(text),
        "unlimited": _is_unlimited(text),
        "brands": _brand_tokens(text),
        "core": _canonical_condition_text(text),
    }


def _same_condition(old_value: str, new_value: str) -> bool:
    old_sig = _condition_signature(old_value)
    new_sig = _condition_signature(new_value)
    if old_sig == new_sig:
        return True
    if old_sig["availability"] != new_sig["availability"]:
        return False
    if old_sig["unlimited"] != new_sig["unlimited"]:
        return False
    if old_sig["brands"] != new_sig["brands"]:
        return False

    old_numbers, new_numbers = old_sig["numbers"], new_sig["numbers"]
    if old_numbers or new_numbers:
        return old_numbers == new_numbers

    old_core, new_core = old_sig["core"], new_sig["core"]
    if old_core == new_core:
        return True
    if old_core and new_core and (old_core in new_core or new_core in old_core):
        return True
    return False


def change_kind(field_id: str, old_value: str, new_value: str) -> str:
    """Разводит изменения на рыночные (market) и технические (service).

    market — изменение условий продукта у банка: оба значения были
    фактически найдены и содержательно отличаются.
    service — работа самого сервиса: дозаполнение пустых полей, пропажа
    данных из источника, справочные поля, переформулировки того же значения.
    """
    if field_id in REFERENCE_FIELDS:
        return "service"
    if old_value == NOT_FOUND and new_value != NOT_FOUND:
        return "service"  # дозаполнение нашей базы, а не изменение у банка
    if new_value == NOT_FOUND:
        return "service"  # данные пропали из источника — техпроблема
    if _normalize(old_value) == _normalize(new_value):
        return "service"  # то же значение, другая пунктуация/регистр
    if _same_condition(old_value, new_value):
        return "service"  # переформулировка тех же условий
    return "market"


# Дата, с которой ведётся рыночный лог (разделение market/service).
# Сравнения «через» рефакторинги схемы до этой даты не учитываются.
MARKET_LOG_STARTED = "2026-07-02"


def append_log(path: Path, entries: list, cap: int = None):
    """Дописывает записи в JSON-лог (массив). Файл создаётся даже при нуле
    записей — отсутствие файла не должно выглядеть как ошибка пайплайна."""
    existing = []
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            existing = json.load(fh)
    existing.extend(entries)
    if cap:
        existing = existing[-cap:]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, ensure_ascii=False, indent=1)


def _change_source(field) -> str:
    """Откуда взято новое значение (для changelog); ручные уточнения помечаются."""
    if not isinstance(field, dict):
        return ""
    name = field.get("source_name", "")
    if field.get("source_id") == "curated":
        return f"{name} — ручное уточнение от {field.get('date_checked', '')}"
    return name


def load_history(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {"scans": [], "changelog": []}


def save_history(history: dict, path: Path):
    history["scans"] = history["scans"][-MAX_SCANS_KEPT:]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(history, fh, ensure_ascii=False, indent=1)


def diff_results(prev_scan: dict, new_scan: dict, field_labels: dict) -> list:
    """Сравнивает поля тиров двух сканов. Возвращает список изменений."""
    changes = []
    prev_results = prev_scan.get("results", {})
    new_results = new_scan.get("results", {})

    for tier_id, new_entry in new_results.items():
        prev_entry = prev_results.get(tier_id)
        if prev_entry is None:
            # Тиры появляются/исчезают только через правку нашего реестра
            # (sources.py) — это событие сервиса, не рынка. Реальный запуск
            # нового тира банком фиксируйте рыночной записью вручную или
            # через последующие изменения полей
            changes.append({
                "scan_date": new_scan["date"],
                "prev_date": prev_scan.get("date", ""),
                "bank": new_entry["bank"],
                "tier": new_entry["tier"],
                "field": "—",
                "old": "(тир отсутствовал в реестре)",
                "new": "тир добавлен в реестр сканера",
                "kind": "service",
                "source": "",
                "source_url": "",
            })
            continue
        for field_id, new_field in new_entry.get("fields", {}).items():
            if field_id in REFERENCE_FIELDS:
                continue
            old_field = prev_entry.get("fields", {}).get(field_id)
            if old_field is None:
                continue
            old_value, new_value = field_value(old_field), field_value(new_field)
            if old_value != new_value:
                changes.append({
                    "scan_date": new_scan["date"],
                    "prev_date": prev_scan.get("date", ""),
                    "bank": new_entry["bank"],
                    "tier": new_entry["tier"],
                    "field": field_labels.get(field_id, field_id),
                    "old": old_value,
                    "new": new_value,
                    "kind": change_kind(field_id, old_value, new_value),
                    "source": _change_source(new_field),
                    "source_url": (new_field.get("source_url", "")
                                   if isinstance(new_field, dict) else ""),
                })

    for tier_id, prev_entry in prev_results.items():
        if tier_id not in new_results:
            changes.append({
                "scan_date": new_scan["date"],
                "prev_date": prev_scan.get("date", ""),
                "bank": prev_entry["bank"],
                "tier": prev_entry["tier"],
                "field": "—",
                "old": "тир был в реестре",
                "new": "тир исключён из реестра сканера",
                "kind": "service",
                "source": "",
                "source_url": "",
            })
    return changes


def schema_changes(prev_scan: dict, new_scan: dict, field_labels: dict) -> list:
    """Изменения методологии отчёта: поля, появившиеся/исчезнувшие в схеме.
    Фиксируются одной системной записью на поле — это не изменение условий
    у банка, а рефакторинг структуры данных."""
    def field_ids(scan):
        ids = set()
        for entry in scan.get("results", {}).values():
            ids.update(entry.get("fields", {}).keys())
        return ids

    prev_ids, new_ids = field_ids(prev_scan), field_ids(new_scan)
    changes = []
    for fid in sorted(new_ids - prev_ids):
        changes.append({
            "scan_date": new_scan["date"],
            "prev_date": prev_scan.get("date", ""),
            "bank": "— система —",
            "tier": "все банки",
            "field": field_labels.get(fid, fid),
            "old": "(поля не было в схеме отчёта)",
            "new": "поле добавлено в схему",
            "kind": "service",
            "source": "изменение методологии отчёта",
        })
    for fid in sorted(prev_ids - new_ids):
        changes.append({
            "scan_date": new_scan["date"],
            "prev_date": prev_scan.get("date", ""),
            "bank": "— система —",
            "tier": "все банки",
            "field": field_labels.get(fid, fid),
            "old": "поле было в схеме",
            "new": "(поле удалено из схемы отчёта)",
            "kind": "service",
            "source": "изменение методологии отчёта",
        })
    return changes


def merge_partial_scan(history: dict, new_scan: dict) -> dict:
    """При точечном скане (--scan-bank/--scan-lifestyle) дополняем новый скан
    последними известными данными по остальным тирам, чтобы отчёт оставался полным,
    а diff не показывал ложные 'тир пропал'."""
    if not history["scans"]:
        return new_scan
    last = history["scans"][-1]
    merged_results = dict(last.get("results", {}))
    merged_results.update(new_scan["results"])
    new_scan["results"] = merged_results
    return new_scan
