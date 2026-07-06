# -*- coding: utf-8 -*-
"""Feedback history, diff and trend helpers."""

import json
from pathlib import Path

MAX_FEEDBACK_SCANS_KEPT = 20


def load_feedback_history(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {"scans": [], "changelog": []}


def save_feedback_history(history: dict, path: Path):
    history["scans"] = history.get("scans", [])[-MAX_FEEDBACK_SCANS_KEPT:]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(history, fh, ensure_ascii=False, indent=1)


def diff_feedback(prev_scan: dict, new_scan: dict) -> list:
    prev_ids = {r["review_id"] for r in prev_scan.get("reviews", [])}
    changes = []
    for review in new_scan.get("reviews", []):
        if review["review_id"] not in prev_ids:
            changes.append({
                "scan_date": new_scan["date"],
                "prev_date": prev_scan.get("date", ""),
                "kind": "new_review",
                "source": review.get("source_name", ""),
                "product_id": review.get("product_id", ""),
                "review_id": review["review_id"],
                "summary": review.get("text", "")[:180],
                "url": review.get("url", ""),
            })
    for topic, current in new_scan.get("trends", {}).get("topic_counts", {}).items():
        previous = prev_scan.get("trends", {}).get("topic_counts", {}).get(topic, 0)
        if current > previous and current >= 2:
            changes.append({
                "scan_date": new_scan["date"],
                "prev_date": prev_scan.get("date", ""),
                "kind": "rising_topic",
                "source": "feedback analysis",
                "product_id": "",
                "review_id": "",
                "summary": f"{topic}: {previous} → {current}",
                "url": "",
            })
    return changes


def build_trends(reviews: list, analyses: dict, emerging_topics: list) -> dict:
    topic_counts = {}
    sentiment_counts = {
        "Очень негативный": 0,
        "Негативный": 0,
        "Нейтральный": 0,
        "Позитивный": 0,
        "Очень позитивный": 0,
    }
    by_source = {}
    by_product = {}
    monthly = {}
    by_category_sentiment = {}
    for review in reviews:
        analysis = analyses.get(review.review_id, {})
        sentiment = analysis.get("sentiment", "Нейтральный")
        sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
        by_source[review.source_id] = by_source.get(review.source_id, 0) + 1
        by_product[review.product_id] = by_product.get(review.product_id, 0) + 1
        month = (review.published_at or review.date or review.collected_at)[:7]
        monthly[month] = monthly.get(month, 0) + 1
        for topic in analysis.get("topics", []):
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
            by_category_sentiment.setdefault(topic, {}).setdefault(sentiment, 0)
            by_category_sentiment[topic][sentiment] += 1
    return {
        "topic_counts": dict(sorted(topic_counts.items(), key=lambda x: (-x[1], x[0]))),
        "sentiment_counts": sentiment_counts,
        "source_counts": dict(sorted(by_source.items())),
        "product_counts": dict(sorted(by_product.items())),
        "monthly_counts": dict(sorted(monthly.items())),
        "category_sentiment": by_category_sentiment,
        "emerging_topics": emerging_topics,
    }
