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
    return frozenset(re.findall(r"\d+(?:[.,]\d+)?", text or ""))


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
    old_nums, new_nums = _nums(old_value), _nums(new_value)
    if old_nums and new_nums and old_nums == new_nums:
        return "service"  # переформулировка: все цифры совпадают
    return "market"


def append_log(path: Path, entries: list, cap: int = None):
    """Дописывает записи в JSON-лог (массив)."""
    if not entries:
        return
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
