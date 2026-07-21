# -*- coding: utf-8 -*-
"""JSON export used as the single source for the Sber VS HTML landing."""

import json
from datetime import datetime
from pathlib import Path

from scanner.benefits import other_benefits_text
from scanner.formatting import normalize_source_text
from scanner.merge import field_value
from scanner.sources import (
    BANK_FIELDS,
    BANKS,
    NOT_FOUND,
    NOT_FOUND_AVAILABLE,
    REFERENCE_FIELDS,
    SOURCE_META,
    source_priority_rank,
)

SCHEMA_VERSION = 1

GPB_PREMIUM_TIERS = {"gpb_premium_1", "gpb_premium_2", "gpb_premium_3"}
GPB_TRAVEL_OPTION_FIELDS = {"lounge_access", "taxi", "insurance"}

DISPLAY_BANK_FIELD_IDS = [
    fid for fid in BANK_FIELDS
    if fid not in {
        "taxi_restaurants",
        "always_included_options",
        "selectable_options",
        "selection_rules",
        "auto",
        "ecosystem",
    }
]


def write_comparison_json(history: dict, output_path: Path) -> dict:
    """Write structured comparison data for HTML and return the payload."""
    payload = build_comparison_json(history)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def build_comparison_json(history: dict) -> dict:
    last_scan = history["scans"][-1] if history.get("scans") else {
        "results": {}, "meta": {}, "date": ""}
    results = last_scan.get("results", {})
    scan_date = last_scan.get("date", "")
    rows = []
    for bank in BANKS:
        if bank["type"] not in {"our", "bank", "intl"}:
            continue
        for tier in bank["tiers"]:
            entry = results.get(tier["tier_id"])
            if not entry:
                continue
            rows.append(_entry_record(bank, tier, entry, scan_date))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scan_date": scan_date,
        "source_of_truth": "json",
        "source_policy": (
            "HTML consumes this JSON only. Excel is a report view and is not "
            "read by the landing generator."
        ),
        "rows": rows,
    }


def _entry_record(bank: dict, tier: dict, entry: dict, scan_date: str) -> dict:
    fields = entry.get("fields", {})
    records = {
        fid: _field_record(
            field_id=fid,
            field=_display_field(fields, fid),
            bank_id=bank["id"],
            bank_name=bank["name"],
            tier_id=tier["tier_id"],
            tier_name=tier["tier_name"],
            scan_date=entry.get("scan_date", scan_date),
        )
        for fid in DISPLAY_BANK_FIELD_IDS
    }
    return {
        "bank_id": bank["id"],
        "bank": bank["name"],
        "tier_id": tier["tier_id"],
        "tier": tier["tier_name"],
        "segment": tier.get("segment") or entry.get("segment", ""),
        "scan_date": entry.get("scan_date", scan_date),
        "sources_ok": entry.get("sources_ok", ""),
        "source_url": entry.get("source_url", ""),
        "status": entry.get("status", ""),
        "score": entry.get("score", {}),
        "fields": records,
    }


def _display_field(fields: dict, fid: str):
    if fid == "other_benefits":
        field = fields.get(fid)
        if isinstance(field, dict):
            return field
        derived = other_benefits_text(fields)
        return {
            "value": derived,
            "source_id": "derived",
            "source_type": "derived",
            "source_name": "Нормализация",
            "raw_text": derived,
            "publication_status": "blocked" if derived == NOT_FOUND else "published",
            "publication_reason": "derived other_benefits without item provenance",
        }
    return fields.get(fid)


def _field_record(field_id: str, field, bank_id: str, bank_name: str,
                  tier_id: str, tier_name: str, scan_date: str) -> dict:
    value = field_value(field)
    display_value = _display_value(value, field_id)
    display_value = _option_display_value(display_value, field_id, tier_id)
    if isinstance(field, dict):
        raw_text = field.get("raw_text") or field.get("value") or ""
        source_id = field.get("source_id", "")
        source_type = field.get("source_type") or _source_type(source_id)
        source_url = field.get("source_url", "")
        date_checked = field.get("date_checked", "")
        note = field.get("note", "")
        publication_status = field.get("publication_status", "")
        publication_reason = field.get("publication_reason", "")
        conflict_status = field.get("conflict_status", "")
        divergent = bool(field.get("divergent"))
        alternatives = _normalize_alternatives(field.get("alternatives", []))
        blocked_value = field.get("blocked_value", "")
        quality = field.get("quality", "")
    else:
        raw_text = value or ""
        source_id = ""
        source_type = ""
        source_url = ""
        date_checked = ""
        note = ""
        publication_status = ""
        publication_reason = ""
        conflict_status = ""
        divergent = False
        alternatives = []
        blocked_value = ""
        quality = ""
    return {
        "bank_id": bank_id,
        "bank": bank_name,
        "tier_id": tier_id,
        "level": tier_name,
        "field_id": field_id,
        "field": BANK_FIELDS.get(field_id, {}).get("label", field_id),
        "value": _raw_value(value, field_id),
        "display_value": display_value,
        "raw_text": _raw_value(raw_text, field_id),
        "source_id": source_id,
        "source_type": source_type,
        "source_priority": source_priority_rank(source_id),
        "source_url": source_url,
        "retrieved_at": date_checked or (scan_date or "")[:10],
        "document_date": "",
        "date_checked": date_checked,
        "quality": quality,
        "status": _publication_status(value, publication_status, conflict_status, divergent),
        "publication_status": publication_status,
        "publication_reason": publication_reason,
        "conflict_status": conflict_status,
        "divergent": divergent,
        "alternatives": alternatives,
        "blocked_value": blocked_value,
        "note": normalize_source_text(note),
        "is_reference": field_id in REFERENCE_FIELDS,
    }


def _option_display_value(display_value: str, field_id: str, tier_id: str) -> str:
    if tier_id not in GPB_PREMIUM_TIERS:
        return display_value
    if field_id not in GPB_TRAVEL_OPTION_FIELDS:
        return display_value
    if display_value in {NOT_FOUND, NOT_FOUND_AVAILABLE}:
        return display_value
    if display_value.startswith("Опция на выбор:"):
        return display_value
    return f"Опция на выбор: Путешествия — {display_value}"


def _normalize_alternatives(alternatives):
    if not isinstance(alternatives, list):
        return []
    normalized = []
    for item in alternatives:
        if isinstance(item, dict):
            next_item = {}
            for key, value in item.items():
                if isinstance(value, str) and key in {"value", "display_value", "raw_text", "note"}:
                    next_item[key] = normalize_source_text(value)
                else:
                    next_item[key] = value
            normalized.append(next_item)
        else:
            normalized.append(item)
    return normalized


def _raw_value(value, field_id: str = "") -> str:
    if value in (None, ""):
        return NOT_FOUND
    if field_id == "other_benefits":
        lines = [
            normalize_source_text(line)
            for line in str(value).splitlines()
            if line.strip()
        ]
        return "\n".join(lines) if lines else NOT_FOUND
    return normalize_source_text(value)


def _display_value(value, field_id: str = "") -> str:
    normalized = _raw_value(value, field_id)
    if normalized.strip().lower() == NOT_FOUND:
        return NOT_FOUND_AVAILABLE
    return normalized


def _source_type(source_id: str) -> str:
    return SOURCE_META.get(source_id, {}).get("source_type", source_id)


def _publication_status(value, publication_status: str, conflict_status: str,
                        divergent: bool) -> str:
    if _raw_value(value).strip().lower() == NOT_FOUND:
        return "not_found"
    if publication_status == "blocked":
        return "blocked"
    if divergent or conflict_status == "conflict":
        return "source_conflict"
    if publication_status == "published":
        return "verified"
    return "needs_review"
