# -*- coding: utf-8 -*-
"""Parse public HTML pages into raw feedback records."""

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from scanner.feedback_merge import attribute_product, detect_language
from scanner.feedback_sources import get_source
from scanner.parse import normalize_text


def parse_manual_seed(path: Path, collected_at: str) -> tuple:
    """Read manually curated public reviews from JSONL.

    Each line may contain any FeedbackReview-compatible field. Missing
    provenance is filled with local/manual metadata.
    """
    if not path.exists():
        return [], {"status": "ok", "message": "seed file not found", "parsed": 0}
    records = []
    with open(path, encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            item.setdefault("source_id", "manual_seed")
            item.setdefault("source_name", "Manual seed JSONL")
            item.setdefault("url", "")
            item.setdefault("date", collected_at[:10])
            item.setdefault("author", "")
            item.setdefault("provenance", {})
            item["provenance"].update({
                "source_url": item.get("url", ""),
                "fetched_via": "manual_seed",
                "raw_path": str(path),
                "parser": "manual_seed_jsonl",
                "date_checked": collected_at[:10],
                "robots_status": "manual",
                "extraction_quality": "manual",
            })
            records.append(item)
    return records, {"status": "ok", "message": "", "parsed": len(records)}


def parse_generic_html(html: str, url: str, source_id: str, collected_at: str,
                       raw_path: str = "", product_id: str = "") -> list:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    source = get_source(source_id) or {"name": source_id}
    candidates = _candidate_blocks(soup)
    records = []
    for idx, block in enumerate(candidates, start=1):
        text = normalize_text(block.get_text(" ", strip=True))
        detected_product = product_id or attribute_product(text, url)
        if not _looks_like_feedback(text, detected_product):
            continue
        rating = _extract_rating(text)
        author = _extract_author(block)
        date = _extract_date(block) or collected_at[:10]
        records.append({
            "source_id": source_id,
            "source_name": source["name"],
            "url": url,
            "date": date,
            "published_at": date,
            "scanned_at": collected_at,
            "author": author,
            "title": _extract_title(block),
            "text": text[:3000],
            "full_text": text[:3000],
            "pros": "",
            "cons": "",
            "comments": "",
            "rating": rating,
            "likes_count": _extract_counter(text, ("лайк", "like")),
            "comments_count": _extract_counter(text, ("коммент", "comment")),
            "product_id": detected_product,
            "record_type": "review",
            "data_source": source["name"],
            "source_url": url,
            "office": _extract_office(text),
            "language": detect_language(text),
            "provenance": {
                "source_url": url,
                "fetched_via": "requests/playwright",
                "raw_path": raw_path,
                "parser": "generic_html",
                "date_checked": collected_at[:10],
                "robots_status": "allowed",
                "extraction_quality": "snippet",
                "block_index": idx,
            },
        })
    return records


def parse_otzovik(html: str, url: str, source_id: str, collected_at: str,
                  raw_path: str = "") -> list:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    source = get_source(source_id) or {"name": source_id}
    blocks = _otzovik_blocks(soup)
    records = []
    for idx, block in enumerate(blocks, start=1):
        text = normalize_text(block.get_text(" ", strip=True))
        if len(text) < 80:
            continue
        title = _extract_title(block)
        if _looks_otzovik_listing(title, text):
            continue
        date = _extract_date(block)
        if not date or not date.startswith("2026"):
            continue
        pros = _extract_otzovik_labeled(block, ".review-plus", text, ("достоинства", "плюсы"))
        cons = _extract_otzovik_labeled(block, ".review-minus", text, ("недостатки", "минусы"))
        full_text = _extract_otzovik_full_text(block, text)
        records.append({
            "source_id": source_id,
            "source_name": source["name"],
            "url": _extract_review_url(block, url),
            "date": date,
            "published_at": date,
            "scanned_at": collected_at,
            "author": _extract_author(block),
            "title": title,
            "text": full_text[:4000],
            "full_text": full_text[:8000],
            "pros": pros,
            "cons": cons,
            "comments": "",
            "rating": _extract_rating(text) or _extract_otzovik_rating(text),
            "likes_count": _extract_counter(text, ("лайк", "like", "полезн")),
            "comments_count": _extract_counter(text, ("коммент", "comment")),
            "product_id": "sber_premier",
            "record_type": "review",
            "data_source": source["name"],
            "source_url": url,
            "office": _extract_office(text),
            "language": detect_language(text),
            "provenance": {
                "source_url": url,
                "fetched_via": "requests/playwright",
                "raw_path": raw_path,
                "parser": "otzovik",
                "date_checked": collected_at[:10],
                "robots_status": "allowed",
                "extraction_quality": "structured",
                "block_index": idx,
            },
        })
    return records


def _candidate_blocks(soup):
    selectors = [
        "[itemprop='review']",
        "[class*='review']",
        "[class*='comment']",
        "article",
        "li",
    ]
    blocks = []
    seen = set()
    for selector in selectors:
        for block in soup.select(selector):
            text = normalize_text(block.get_text(" ", strip=True))
            key = text[:200]
            if len(text) >= 80 and key not in seen:
                seen.add(key)
                blocks.append(block)
    if blocks:
        return blocks[:100]
    body = soup.body or soup
    return [body]


def _otzovik_blocks(soup):
    blocks = []
    seen = set()
    for selector in (".item.review-wrap", ".item[class*='status']"):
        for block in soup.select(selector):
            text = normalize_text(block.get_text(" ", strip=True))
            key = text[:200]
            if len(text) >= 80 and key not in seen:
                seen.add(key)
                blocks.append(block)
    if blocks:
        return blocks[:50]

    for selector in ("[class*='review']", "article"):
        for block in soup.select(selector):
            text = normalize_text(block.get_text(" ", strip=True))
            key = text[:200]
            if len(text) >= 80 and key not in seen and _mentions_sber_premium(text):
                seen.add(key)
                blocks.append(block)
    return blocks[:50] or _candidate_blocks(soup)


def _mentions_sber_premium(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in (
        "сбербанк премьер", "сберпремьер", "сбер премьер",
        "сбер первый", "сберперв", "sber premier", "sber first",
    ))


def _looks_like_feedback(text: str, product_id: str = "") -> bool:
    low = text.lower()
    premium_markers = [
        "сберпремьер", "сбер премьер", "сберперв", "сбер первый",
        "sber private", "sber premier", "премиальн", "персональный менеджер",
        "пакет премьер", "пакет «премьер»", "private banking",
    ]
    feedback_markers = [
        "отзыв", "жалоб", "проблем", "не работает", "долго", "не дозвон",
        "комис", "списал", "поддержк", "помог", "понрав", "хорош", "плох",
        "ужас", "рейтинг", "снял", "не предупред",
    ]
    if len(text) < 80:
        return False
    if _looks_irrelevant(low):
        return False
    if not _has_customer_experience(low):
        return False
    if product_id and product_id != "unknown":
        return any(marker in low for marker in feedback_markers + premium_markers)
    return any(marker in low for marker in premium_markers) and any(
        marker in low for marker in feedback_markers)


def _has_customer_experience(low: str) -> bool:
    markers = [
        " я ", " мне ", " меня ", " мой ", " моя ", "купил", "подключил",
        "снял", "списал", "не смог", "не могу", "не предупред", "помогите",
        "жалоба", "мой рейтинг", "опыт", "столкнул", "позвонил",
        "поддержка", "менеджер", "не дозвон", "долго",
    ]
    padded = f" {low} "
    return any(marker in padded for marker in markers)


def _looks_irrelevant(low: str) -> bool:
    head = low[:500]
    if "сберпрайм" in head and "сберпремьер" not in head and "сбер премьер" not in head:
        return True
    seo_markers = [
        "вклады на 3 месяца",
        "вклады на 1 год",
        "лучшие предложения",
        "актуальных предложений",
        "banki.lab",
    ]
    return any(marker in head for marker in seo_markers)


def _extract_rating(text: str):
    match = re.search(r"([1-5])\s*(?:из|/)\s*5", text)
    if match:
        return float(match.group(1))
    match = re.search(r"(?:оценка|рейтинг)[:\s]+([1-5])", text.lower())
    return float(match.group(1)) if match else None


def _extract_otzovik_rating(text: str):
    match = re.search(
        r"\b(?:россия|москва|санкт-петербург)?\s*([1-5])\s+"
        r"\d{1,2}\s+"
        r"(?:янв|фев|мар|апр|мая|май|июн|июл|авг|сен|сент|окт|ноя|дек)",
        text.lower())
    return float(match.group(1)) if match else None


def _looks_otzovik_listing(title: str, text: str) -> bool:
    low_title = (title or "").lower()
    low = text.lower()
    return (
        " - отзывы" in low_title
        and "добавить отзыв" in low
        and "сортировать" in low
    )


def _extract_title(block) -> str:
    block_text = normalize_text(block.get_text(" ", strip=True))
    match = re.search(r"Отзыв:\s*.+?\s+-\s+(.+?)(?:\s+Достоинства:|\s+Недостатки:|$)", block_text)
    if match:
        return normalize_text(match.group(1))[:240]
    for link in block.find_all("a", href=True):
        href = link.get("href", "")
        if "review_" in href:
            text = normalize_text(link.get_text(" ", strip=True))
            if text and text.lower() != "читать весь отзыв" and not text.isdigit():
                return text[:240]
    for selector in ("h1", "h2", "h3", ".review-title", "[class*='title']"):
        node = block.select_one(selector)
        if node:
            text = normalize_text(node.get_text(" ", strip=True))
            if text:
                return text[:240]
    return ""


def _extract_labeled_text(text: str, labels: tuple) -> str:
    low = text.lower()
    for label in labels:
        idx = low.find(label)
        if idx == -1:
            continue
        tail = text[idx + len(label):]
        stop = len(tail)
        for marker in ("Недостатки", "Достоинства", "Комментарий", "Отзыв", "Оценка"):
            pos = tail.find(marker)
            if pos > 0:
                stop = min(stop, pos)
        return normalize_text(tail[:stop].strip(" :-—"))[:1000]
    return ""


def _extract_otzovik_labeled(block, selector: str, text: str, labels: tuple) -> str:
    node = block.select_one(selector)
    if node:
        value = normalize_text(node.get_text(" ", strip=True))
        value = re.sub(r"^(Достоинства|Недостатки|Плюсы|Минусы)\s*:\s*", "", value, flags=re.I)
        return value[:1000]
    return _extract_labeled_text(text, labels)


def _extract_otzovik_full_text(block, text: str) -> str:
    body = block.select_one(".review-body.description")
    if body:
        value = normalize_text(body.get_text(" ", strip=True))
        return value[:8000]
    return _strip_otzovik_noise(text)


def _strip_otzovik_noise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_review_url(block, fallback: str) -> str:
    from urllib.parse import urljoin
    if "review_" in fallback:
        return fallback.split("#", 1)[0]
    for node in block.find_all("a", href=True):
        if "review_" in node["href"] and "#comments" not in node["href"]:
            return urljoin(fallback, node["href"])
    node = block.find("a", href=True)
    if not node:
        return fallback
    return urljoin(fallback, node["href"])


def _extract_author(block) -> str:
    for selector in ("[itemprop='author']", "[class*='author']", "[class*='user']"):
        node = block.select_one(selector)
        if node:
            return normalize_text(node.get_text(" ", strip=True))[:120]
    return ""


def _extract_date(block) -> str:
    node = block.find("time")
    if node:
        return (node.get("datetime") or node.get_text(" ", strip=True))[:10]
    text = normalize_text(block.get_text(" ", strip=True))
    match = re.search(r"\b(20\d{2})[-.](\d{2})[-.](\d{2})\b", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    month_map = {
        "янв": "01", "фев": "02", "мар": "03", "апр": "04",
        "мая": "05", "май": "05", "июн": "06", "июл": "07",
        "авг": "08", "сен": "09", "сент": "09", "окт": "10",
        "ноя": "11", "дек": "12",
    }
    match = re.search(
        r"\b(\d{1,2})\s+"
        r"(янв(?:аря)?|фев(?:раля)?|мар(?:та)?|апр(?:еля)?|мая|май|"
        r"июн(?:я)?|июл(?:я)?|авг(?:уста)?|сен(?:тября)?|сент(?:ября)?|"
        r"окт(?:ября)?|ноя(?:бря)?|дек(?:абря)?)\s+"
        r"(20\d{2})\b",
        text.lower())
    if match:
        day = int(match.group(1))
        month_key = match.group(2)[:3]
        if match.group(2) == "мая":
            month_key = "мая"
        month = month_map.get(month_key)
        if month:
            return f"{match.group(3)}-{month}-{day:02d}"
    return ""


def _extract_counter(text: str, markers: tuple):
    low = text.lower()
    for marker in markers:
        match = re.search(rf"(\d+)\s+{marker}", low)
        if match:
            return int(match.group(1))
    return None


def _extract_office(text: str) -> str:
    match = re.search(r"(?:офис|отделение|branch)[:\s]+([^.;|]{5,120})", text, re.IGNORECASE)
    return normalize_text(match.group(1)) if match else ""
