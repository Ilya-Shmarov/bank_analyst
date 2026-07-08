# -*- coding: utf-8 -*-
"""Orchestration for Customer Feedback Intelligence."""

from datetime import datetime
from pathlib import Path

from scanner.diff import MAX_SERVICE_LOG, append_log
from scanner.feedback_analyze import analyze_reviews, build_insights, emerging_topics
from scanner.feedback_diff import (
    build_trends,
    diff_feedback,
    load_feedback_history,
    save_feedback_history,
)
from scanner.feedback_fetch import scan_feedback_sources
from scanner.feedback_merge import (
    append_review_store,
    deduplicate_reviews,
    load_review_store,
    normalize_reviews,
    save_review_store,
)
from scanner.feedback_scoring import build_suggestions


def run_feedback_scan(product_id: str, source_id: str, paths: dict) -> dict:
    scan_dt = datetime.now().isoformat(timespec="seconds")
    raw_records, ok, failed, source_stats = scan_feedback_sources(
        source_id, product_id, scan_dt, paths["raw_feedback_dir"], paths["data_dir"])
    normalized = normalize_reviews(raw_records, scan_dt)
    existing = load_review_store(paths["reviews_path"])
    new_reviews = deduplicate_reviews(normalized, existing)
    append_review_store(paths["reviews_path"], new_reviews)

    all_review_dicts = existing + [review.to_dict() for review in new_reviews]
    all_reviews = normalize_reviews(all_review_dicts, scan_dt)
    save_review_store(paths["reviews_path"], all_reviews)
    history = load_feedback_history(paths["history_path"])
    prev_scan = history["scans"][-1] if history["scans"] else {}
    analyses = analyze_reviews(all_reviews)
    topics = emerging_topics(all_reviews, analyses)
    trends = build_trends(all_reviews, analyses, topics)
    insights = build_insights(all_reviews, analyses, prev_scan)
    suggestions = build_suggestions(all_reviews, analyses, scan_dt)
    new_scan = {
        "date": scan_dt,
        "reviews": [review.to_dict() for review in all_reviews],
        "analyses": analyses,
        "insights": insights,
        "suggestions": suggestions,
        "trends": trends,
        "meta": {
            "mode": "feedback",
            "product_id": product_id or "all",
            "source_id": source_id or "all",
            "sources_ok": ok,
            "sources_failed": failed,
            "source_stats": source_stats,
            "raw_records": len(raw_records),
            "new_reviews": len(new_reviews),
            "total_reviews": len(all_reviews),
        },
    }

    changes = []
    if history["scans"]:
        changes = diff_feedback(history["scans"][-1], new_scan)
        history["changelog"].extend(changes)
    history["scans"].append(new_scan)
    save_feedback_history(history, paths["history_path"])

    service_entries = [
        {"scan_date": scan_dt, "bank": "— feedback —", "tier": name,
         "field": "источник отзывов", "old": "", "new": f"недоступен: {err}",
         "kind": "service", "source": "", "source_url": ""}
        for name, err in failed.items()
    ]
    append_log(paths["service_log_path"], service_entries, cap=MAX_SERVICE_LOG)
    return {"history": history, "scan": new_scan, "changes": changes}


def load_feedback_artifacts(history_path: Path) -> dict:
    return load_feedback_history(history_path)
