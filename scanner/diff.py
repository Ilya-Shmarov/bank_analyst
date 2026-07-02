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
from pathlib import Path

MAX_SCANS_KEPT = 20


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
            changes.append({
                "scan_date": new_scan["date"],
                "prev_date": prev_scan.get("date", ""),
                "bank": new_entry["bank"],
                "tier": new_entry["tier"],
                "field": "—",
                "old": "(тир отсутствовал)",
                "new": "тир добавлен в скан",
            })
            continue
        for field_id, new_value in new_entry.get("fields", {}).items():
            old_value = prev_entry.get("fields", {}).get(field_id)
            if old_value is not None and old_value != new_value:
                changes.append({
                    "scan_date": new_scan["date"],
                    "prev_date": prev_scan.get("date", ""),
                    "bank": new_entry["bank"],
                    "tier": new_entry["tier"],
                    "field": field_labels.get(field_id, field_id),
                    "old": old_value,
                    "new": new_value,
                })

    for tier_id, prev_entry in prev_results.items():
        if tier_id not in new_results:
            changes.append({
                "scan_date": new_scan["date"],
                "prev_date": prev_scan.get("date", ""),
                "bank": prev_entry["bank"],
                "tier": prev_entry["tier"],
                "field": "—",
                "old": "тир был в скане",
                "new": "(тир пропал из скана)",
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
