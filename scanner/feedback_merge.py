# -*- coding: utf-8 -*-
"""Normalize, attribute and deduplicate feedback reviews."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from scanner.feedback_models import FeedbackReview
from scanner.feedback_sources import PRODUCTS


def normalize_reviews(raw_reviews: list, collected_at: str) -> list:
    reviews = []
    for raw in raw_reviews:
        text = _clean_text(raw.get("full_text") or raw.get("text", ""))
        if not text:
            continue
        published_at = (raw.get("published_at") or raw.get("date") or collected_at)[:10]
        if not _is_2026(published_at):
            continue
        url = _canonical_url(raw.get("url", ""))
        product_id = raw.get("product_id") or attribute_product(text, url)
        review_id = raw.get("review_id") or build_review_id(
            raw.get("source_id", ""), url, raw.get("author", ""), published_at, text)
        source_url = raw.get("source_url") or raw.get("url", "")
        reviews.append(FeedbackReview(
            review_id=review_id,
            source_id=raw.get("source_id", ""),
            source_name=raw.get("source_name", raw.get("source_id", "")),
            url=url,
            date=published_at,
            published_at=published_at,
            scanned_at=raw.get("scanned_at", raw.get("collected_at", collected_at)),
            author=raw.get("author", ""),
            title=_clean_text(raw.get("title", "")),
            text=text,
            full_text=text,
            pros=_clean_text(raw.get("pros", "")),
            cons=_clean_text(raw.get("cons", "")),
            comments=_clean_text(raw.get("comments", "")),
            rating=_float_or_none(raw.get("rating")),
            likes_count=_int_or_none(raw.get("likes_count")),
            comments_count=_int_or_none(raw.get("comments_count")),
            product_id=product_id,
            record_type=raw.get("record_type", "review"),
            data_source=raw.get("data_source", raw.get("source_name", raw.get("source_id", ""))),
            source_url=source_url,
            office=raw.get("office", ""),
            language=raw.get("language") or detect_language(text),
            collected_at=raw.get("collected_at", collected_at),
            provenance=raw.get("provenance", {}),
        ))
    return deduplicate_reviews(reviews)


def deduplicate_reviews(reviews: list, existing: list = None) -> list:
    seen = set()
    result = []
    for review in existing or []:
        seen.add(review.review_id if hasattr(review, "review_id") else review["review_id"])
    for review in reviews:
        key = review.review_id
        fuzzy = _fuzzy_key(review)
        if key in seen or fuzzy in seen:
            continue
        seen.add(key)
        seen.add(fuzzy)
        result.append(review)
    return result


def load_review_store(path: Path) -> list:
    if not path.exists():
        return []
    reviews = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                reviews.append(json.loads(line))
    return reviews


def append_review_store(path: Path, reviews: list):
    if not reviews:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for review in reviews:
            data = review.to_dict() if hasattr(review, "to_dict") else review
            fh.write(json.dumps(data, ensure_ascii=False) + "\n")


def save_review_store(path: Path, reviews: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for review in reviews:
            data = review.to_dict() if hasattr(review, "to_dict") else review
            fh.write(json.dumps(data, ensure_ascii=False) + "\n")


def _is_2026(value: str) -> bool:
    return (value or "").startswith("2026")


def attribute_product(text: str, url: str = "") -> str:
    low = f"{text} {url}".lower()
    for product_id, product in PRODUCTS.items():
        if any(alias.lower() in low for alias in product["aliases"]):
            return product_id
    return "unknown"


def build_review_id(source_id: str, url: str, author: str, date: str, text: str) -> str:
    base = "|".join([
        source_id,
        _canonical_url(url),
        (author or "").strip().lower(),
        (date or "")[:10],
        _text_fingerprint(text),
    ])
    return "fb_" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def detect_language(text: str) -> str:
    cyr = len(re.findall(r"[А-Яа-яЁё]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    if cyr >= lat:
        return "ru"
    return "en" if lat else ""


def _canonical_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _text_fingerprint(text: str) -> str:
    normalized = re.sub(r"[^0-9a-zа-яё]+", " ", (text or "").lower()).strip()
    return hashlib.sha1(normalized[:1000].encode("utf-8")).hexdigest()[:16]


def _fuzzy_key(review) -> str:
    return "|".join([
        review.source_id,
        (review.author or "").lower(),
        (review.date or "")[:10],
        _text_fingerprint(review.text),
    ])


def _float_or_none(value):
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value):
    if value in ("", None):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
