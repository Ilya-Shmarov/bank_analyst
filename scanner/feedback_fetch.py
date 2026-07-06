# -*- coding: utf-8 -*-
"""Feedback source adapters."""

import json
import logging
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup

from scanner.fetch import Fetcher
from scanner.feedback_merge import attribute_product
from scanner.feedback_parse import parse_generic_html, parse_manual_seed, parse_otzovik
from scanner.feedback_sources import FEEDBACK_SOURCES, PRODUCTS, get_product, get_source
from scanner.parse import normalize_text
from landing.premium_changes import extract_changes

log = logging.getLogger("scanner.feedback")

MAX_DISCOVERY_TERMS_PER_PRODUCT = 2
MAX_DISCOVERED_PAGES_PER_SOURCE = 8


def scan_feedback_sources(source_id: str, product_id: str, scan_dt: str,
                          raw_dir: Path, data_dir: Path) -> tuple:
    """Return (raw_records, ok_labels, failed_map, source_stats)."""
    sources = _selected_sources(source_id)
    product = get_product(product_id) if product_id else None
    fetcher = Fetcher(raw_dir)
    records, ok, failed, stats = [], [], {}, []
    for source in sources:
        sid = source["id"]
        if product and sid not in ("manual_seed", "generic_public_html"):
            label = f"{source['name']} / {product['name']}"
        else:
            label = source["name"]
        if source["policy"] == "manual_only":
            failed[label] = "manual_only: источник не сканируется автоматически"
            stats.append(_stat(source, "manual_only", 0, 0, "manual only"))
            continue
        if sid == "manual_seed":
            raw, meta = parse_manual_seed(data_dir / "feedback_manual_seed.jsonl", scan_dt)
            raw = _filter_product(raw, product_id)
            records.extend(raw)
            ok.append(label)
            stats.append(_stat(source, meta["status"], 0, len(raw), meta["message"]))
            continue
        if sid == "generic_public_html":
            fetched, parsed, message = _scan_generic_urls(
                fetcher, data_dir / "feedback_urls.json", product_id, scan_dt)
            records.extend(parsed)
            status = _status_for_counts(fetched, message)
            _track_source_status(label, status, message, ok, failed)
            stats.append(_stat(source, status, fetched, len(parsed), message))
            continue
        if sid == "premiumbanking_info":
            fetched, parsed, message = _scan_premiumbanking_info(
                fetcher, source, product_id, scan_dt)
            records.extend(parsed)
            status = _status_for_counts(fetched, message)
            _track_source_status(label, status, message, ok, failed)
            stats.append(_stat(source, status, fetched, len(parsed), message))
            continue
        if source.get("review_parser") == "otzovik":
            fetched, parsed, message = _scan_direct_review_pages(
                fetcher, source, product_id, scan_dt)
            records.extend(parsed)
            status = _status_for_counts(fetched, message)
            _track_source_status(label, status, message, ok, failed)
            stats.append(_stat(source, status, fetched, len(parsed), message))
            continue
        if source.get("search_url"):
            fetched, parsed, message = _scan_discovered_source(
                fetcher, source, product_id, scan_dt)
            records.extend(parsed)
            status = _status_for_counts(fetched, message)
            _track_source_status(label, status, message, ok, failed)
            stats.append(_stat(source, status, fetched, len(parsed), message))
            continue
        failed[label] = f"{source['status']}: нет search adapter для автоматического сбора"
        stats.append(_stat(source, source["status"], 0, 0, "no search adapter"))
    return records, ok, failed, stats


def _selected_sources(source_id: str):
    if source_id:
        source = get_source(source_id)
        if source is None:
            raise ValueError(f"feedback source '{source_id}' not found")
        return [source]
    return FEEDBACK_SOURCES


def _scan_generic_urls(fetcher: Fetcher, path: Path, product_id: str, scan_dt: str):
    if not path.exists():
        return 0, [], "data/feedback_urls.json not found"
    with open(path, encoding="utf-8") as fh:
        items = json.load(fh)
    parsed = []
    fetched = 0
    for idx, item in enumerate(items, start=1):
        if product_id and item.get("product_id") not in ("", None, product_id):
            continue
        source_id = item.get("source_id", "generic_public_html")
        urls = [item["url"]] if isinstance(item.get("url"), str) else item.get("urls", [])
        if not urls:
            continue
        result = fetcher.fetch(urls, f"feedback_{source_id}_{idx}", scan_dt[:10])
        if result.status != "ok":
            log.warning("  [feedback fail] %s — %s (%s)", urls[0], result.status, result.error)
            continue
        fetched += 1
        raw_path = str(fetcher.raw_dir / scan_dt[:10] / f"feedback_{source_id}_{idx}.html")
        parsed.extend(parse_generic_html(
            result.html, result.url, source_id, scan_dt, raw_path, item.get("product_id", "")))
    return fetched, parsed, ""


def _scan_direct_review_pages(fetcher: Fetcher, source: dict, product_id: str,
                              scan_dt: str):
    fetched = 0
    parsed = []
    page_limit = source.get("max_pages", 1)
    seen_urls = set()
    queue = list(source.get("urls", []))
    page_idx = 0
    while queue and page_idx < page_limit:
        url = queue.pop(0)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        page_idx += 1
        result = fetcher.fetch([url], f"feedback_{source['id']}_{page_idx}", scan_dt[:10])
        if result.status != "ok":
            log.warning("  [feedback direct fail] %s — %s (%s)",
                        url, result.status, result.error)
            continue
        fetched += 1
        raw_path = str(fetcher.raw_dir / scan_dt[:10] / f"feedback_{source['id']}_{page_idx}.html")
        if source.get("review_parser") == "otzovik":
            page_records = parse_otzovik(
                result.html, result.url, source["id"], scan_dt, raw_path)
            parsed.extend(_fetch_otzovik_detail_records(
                fetcher, source, page_records, scan_dt, page_idx) or page_records)
            if page_records:
                next_url = _extract_next_page_url(result.html, result.url)
                if next_url and next_url not in seen_urls:
                    queue.append(next_url)
            continue
        parsed.extend(parse_generic_html(
            result.html, result.url, source["id"], scan_dt, raw_path, product_id or ""))
    return fetched, parsed, f"direct_pages={fetched}; parsed_records={len(parsed)}"


def _fetch_otzovik_detail_records(fetcher: Fetcher, source: dict, page_records: list,
                                  scan_dt: str, page_idx: int) -> list:
    parsed = []
    seen_urls = set()
    for record_idx, record in enumerate(page_records, start=1):
        url = record.get("url", "")
        if "review_" not in url or url in seen_urls:
            continue
        seen_urls.add(url)
        raw_name = f"feedback_{source['id']}_detail_{page_idx}_{record_idx}"
        result = fetcher.fetch([url], raw_name, scan_dt[:10])
        if result.status != "ok":
            log.warning("  [feedback detail fail] %s — %s (%s)",
                        url, result.status, result.error)
            continue
        raw_path = str(fetcher.raw_dir / scan_dt[:10] / f"{raw_name}.html")
        detail_records = parse_otzovik(
            result.html, result.url, source["id"], scan_dt, raw_path)
        if detail_records:
            parsed.extend(detail_records)
    return parsed


def _extract_next_page_url(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for selector in ("a.next[href]", "link[rel='next'][href]"):
        node = soup.select_one(selector)
        if node:
            return urljoin(base_url, node.get("href", ""))
    return ""


def _scan_premiumbanking_info(fetcher: Fetcher, source: dict, product_id: str,
                              scan_dt: str):
    fetched = 0
    parsed = []
    urls = source.get("urls", [])
    for idx, url in enumerate(urls, start=1):
        inferred_product = _pbi_product_id(url)
        if product_id and inferred_product not in ("", product_id):
            continue
        result = fetcher.fetch([url], f"feedback_pbi_{idx}", scan_dt[:10])
        if result.status != "ok":
            log.warning("  [feedback pbi fail] %s — %s (%s)",
                        url, result.status, result.error)
            continue
        fetched += 1
        raw_path = str(fetcher.raw_dir / scan_dt[:10] / f"feedback_pbi_{idx}.html")
        if url.rstrip("/").endswith("/sber"):
            changes = extract_changes(result.html)
            for change_idx, change in enumerate(changes, start=1):
                text = f"premiumbanking.info: {change['date']} — {change['text']}"
                detected_product = attribute_product(text, result.url)
                parsed.append(_pbi_record(
                    source, result.url, scan_dt, text, raw_path,
                    detected_product if detected_product != "unknown" else "sber_premium",
                    change_idx))
            continue
        summary = _pbi_page_summary(result.html)
        if summary:
            parsed.append(_pbi_record(
                source, result.url, scan_dt, summary, raw_path, inferred_product, idx))
    return fetched, parsed, f"pbi_pages={fetched}; parsed_records={len(parsed)}"


def _pbi_record(source: dict, url: str, scan_dt: str, text: str, raw_path: str,
                product_id: str, index: int) -> dict:
    return {
        "source_id": source["id"],
        "source_name": source["name"],
        "url": url,
        "date": scan_dt[:10],
        "published_at": scan_dt[:10],
        "scanned_at": scan_dt,
        "author": "premiumbanking.info",
        "title": "premiumbanking.info: изменения и условия премиальной линейки",
        "text": text,
        "full_text": text,
        "pros": "",
        "cons": "",
        "comments": "",
        "rating": None,
        "likes_count": None,
        "comments_count": None,
        "product_id": product_id or "unknown",
        "record_type": "market_signal",
        "data_source": source["name"],
        "source_url": url,
        "office": "",
        "language": "ru",
        "provenance": {
            "source_url": url,
            "fetched_via": "requests/playwright",
            "raw_path": raw_path,
            "parser": "premiumbanking_info",
            "date_checked": scan_dt[:10],
            "robots_status": "allowed",
            "extraction_quality": "structured",
            "block_index": index,
        },
    }


def _pbi_product_id(url: str) -> str:
    tail = url.rstrip("/").split("/")[-1]
    if tail in {"1", "2", "3"}:
        return "sber_premier"
    if tail in {"4", "5"}:
        return "sber_first"
    if tail == "6":
        return "sber_private"
    return ""


def _pbi_page_summary(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = normalize_text(h1.get_text(" ", strip=True)) if h1 else ""
    rows = []
    for dt in soup.find_all("dt")[:8]:
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        label = normalize_text(dt.get_text(" ", strip=True))
        value = normalize_text(dd.get_text(" ", strip=True))
        if label and value:
            rows.append(f"{label}: {value}")
    if not rows:
        return ""
    prefix = f"premiumbanking.info — {title}. " if title else "premiumbanking.info. "
    return (prefix + " | ".join(rows))[:3000]


def _scan_discovered_source(fetcher: Fetcher, source: dict, product_id: str,
                            scan_dt: str):
    search_urls = _search_urls(source, product_id)
    fetched = 0
    parsed = []
    discovered = []
    seen_urls = set()

    for idx, url in enumerate(search_urls, start=1):
        result = fetcher.fetch([url], f"feedback_search_{source['id']}_{idx}", scan_dt[:10])
        if result.status != "ok":
            log.warning("  [feedback search fail] %s — %s (%s)",
                        url, result.status, result.error)
            continue
        fetched += 1
        for link in _extract_result_links(result.html, result.url, source):
            if link in seen_urls:
                continue
            seen_urls.add(link)
            discovered.append(link)
            if len(discovered) >= MAX_DISCOVERED_PAGES_PER_SOURCE:
                break
        if len(discovered) >= MAX_DISCOVERED_PAGES_PER_SOURCE:
            break

    for idx, url in enumerate(discovered, start=1):
        result = fetcher.fetch([url], f"feedback_page_{source['id']}_{idx}", scan_dt[:10])
        if result.status != "ok":
            log.warning("  [feedback page fail] %s — %s (%s)",
                        url, result.status, result.error)
            continue
        fetched += 1
        raw_path = str(fetcher.raw_dir / scan_dt[:10] / f"feedback_page_{source['id']}_{idx}.html")
        parsed.extend(parse_generic_html(
            result.html, result.url, source["id"], scan_dt, raw_path, product_id or ""))

    message = f"search_pages={len(search_urls)}; discovered_pages={len(discovered)}"
    return fetched, parsed, message


def _search_urls(source: dict, product_id: str) -> list:
    template = source.get("search_url", "")
    if not template:
        return []
    products = {product_id: PRODUCTS[product_id]} if product_id else PRODUCTS
    urls = []
    for product in products.values():
        terms = product.get("search_terms") or product.get("aliases", [])
        for term in terms[:MAX_DISCOVERY_TERMS_PER_PRODUCT]:
            urls.append(template.format(query=quote_plus(term)))
    return urls


def _extract_result_links(html: str, base_url: str, source: dict) -> list:
    soup = BeautifulSoup(html, "html.parser")
    base_host = urlparse(base_url).netloc.lower()
    links = []
    for node in soup.find_all("a", href=True):
        href = urljoin(base_url, node["href"])
        parsed = urlparse(href)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc.lower() != base_host:
            continue
        if _skip_link(parsed.path):
            continue
        text = normalize_text(node.get_text(" ", strip=True))
        href_low = href.lower()
        text_low = text.lower()
        if not _looks_relevant_link(text_low, href_low):
            continue
        clean = parsed._replace(query="", fragment="").geturl().rstrip("/")
        if clean not in links:
            links.append(clean)
    return links


def _skip_link(path: str) -> bool:
    low = path.lower()
    skipped = (
        "/login", "/auth", "/signup", "/register", "/tag/", "/tags/",
        "/search", "/company/", "/users/", "/u/", "/about", "/terms",
        "/community/", "/communities/", "/@", "/people/", "/user/",
    )
    return any(item in low for item in skipped) or low in ("", "/")


def _looks_relevant_link(text_low: str, href_low: str) -> bool:
    markers = [
        "сбер", "sber", "премьер", "premium", "private", "прайват",
        "персональный", "отзыв", "банк",
    ]
    return any(marker in text_low or marker in href_low for marker in markers)


def _filter_product(records: list, product_id: str) -> list:
    if not product_id:
        return records
    return [record for record in records if record.get("product_id") in ("", None, product_id)]


def _stat(source: dict, status: str, fetched: int, parsed: int, message: str) -> dict:
    return {
        "source_id": source["id"],
        "source_name": source["name"],
        "kind": source.get("kind", ""),
        "review_parser": source.get("review_parser", ""),
        "policy": source.get("policy", ""),
        "status": status,
        "date_filter_year": source.get("date_filter_year", 2026),
        "fetched_count": fetched,
        "parsed_count": parsed,
        "message": message,
    }


def _status_for_counts(fetched: int, message: str) -> str:
    if fetched > 0:
        return "ok"
    if "not found" in (message or ""):
        return "not_configured"
    return "unavailable"


def _track_source_status(label: str, status: str, message: str, ok: list, failed: dict):
    if status == "ok":
        ok.append(label)
    elif status != "not_configured":
        failed[label] = f"{status}: {message}"
