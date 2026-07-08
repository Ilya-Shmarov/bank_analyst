# -*- coding: utf-8 -*-
"""Feedback source registry and product aliases."""

PRODUCTS = {
    "sber_premier": {
        "name": "СберПремьер",
        "search_terms": ["СберПремьер отзывы", "СберПремьер жалоба"],
        "aliases": [
            "СберПремьер",
            "Сбер Премьер",
            "пакет СберПремьер",
            "пакет Премьер",
            "пакет «Премьер»",
            "Sber Premier",
            "Premium Banking Сбер",
            "премиальное обслуживание Сбер",
        ],
    },
    "sber_first": {
        "name": "СберПервый",
        "search_terms": ["СберПервый отзывы", "Сбер Первый жалоба"],
        "aliases": [
            "СберПервый",
            "Сбер Первый",
            "Sber First",
            "Сбер первый премиум",
            "персональный менеджер Сбер",
        ],
    },
    "sber_private": {
        "name": "Sber Private Banking",
        "search_terms": ["Sber Private Banking отзывы", "Сбер Private жалоба"],
        "aliases": [
            "Sber Private Banking",
            "Sber Private",
            "Сбер Private",
            "Сбер Прайват",
            "Сбер private banking",
        ],
    },
}


FEEDBACK_SOURCES = [
    {
        "id": "manual_seed",
        "name": "Manual seed JSONL",
        "kind": "manual",
        "policy": "local_seed",
        "status": "available",
        "description": "Локальный data/feedback_manual_seed.jsonl для вручную отобранных публичных отзывов.",
        "review_parser": "manual_seed",
        "supports_date_sort": False,
        "date_filter_year": 2026,
        "urls": [],
    },
    {
        "id": "generic_public_html",
        "name": "Generic public HTML URLs",
        "kind": "generic_html",
        "policy": "robots_checked",
        "status": "available",
        "description": "Опциональный data/feedback_urls.json со списком публичных URL, проверяемых через Fetcher.",
        "review_parser": "generic_html",
        "supports_date_sort": False,
        "date_filter_year": 2026,
        "urls": [],
    },
    {
        "id": "premiumbanking_info",
        "name": "premiumbanking.info",
        "kind": "aggregator",
        "policy": "robots_checked",
        "status": "available",
        "description": "Открытые страницы ПБИ по Сберу: последние изменения и внешние сигналы по премиальным программам.",
        "review_parser": "premiumbanking_info",
        "supports_date_sort": False,
        "date_filter_year": 2026,
        "urls": [
            "https://premiumbanking.info/sber",
            "https://premiumbanking.info/sber/1",
            "https://premiumbanking.info/sber/2",
            "https://premiumbanking.info/sber/3",
            "https://premiumbanking.info/sber/4",
            "https://premiumbanking.info/sber/5",
            "https://premiumbanking.info/sber/6",
        ],
    },
    {
        "id": "otzovik",
        "name": "Отзовик",
        "kind": "review_platform",
        "policy": "robots_checked",
        "status": "available",
        "description": "Отзывы о персональном банковском обслуживании Сбербанк Премьер, сортировка по дате.",
        "review_parser": "otzovik",
        "supports_date_sort": True,
        "date_filter_year": 2026,
        "max_pages": 8,
        "urls": [
            "https://otzovik.com/reviews/personalnoe_bankovskoe_obsluzhivanie_sberbank_premer/?order=date_desc",
        ],
    },
    {
        "id": "banki_ru",
        "name": "Banki.ru",
        "kind": "banking_platform",
        "policy": "manual_only",
        "status": "manual_only",
        "description": "Использовать только вручную, если конкретная review-страница разрешена robots.txt.",
        "review_parser": "manual_only",
        "supports_date_sort": False,
        "date_filter_year": 2026,
        "urls": ["https://www.banki.ru/"],
    },
    {
        "id": "sravni",
        "name": "Sravni",
        "kind": "banking_platform",
        "policy": "robots_checked",
        "status": "restricted",
        "description": "Broad disallow для динамических/review-like путей; каждый URL проверяется отдельно.",
        "review_parser": "generic_html",
        "supports_date_sort": False,
        "date_filter_year": 2026,
        "urls": ["https://www.sravni.ru/"],
    },
    {"id": "bankiros", "name": "Bankiros", "kind": "banking_platform", "policy": "robots_checked", "status": "restricted", "review_parser": "generic_html", "supports_date_sort": False, "date_filter_year": 2026, "urls": ["https://bankiros.ru/"]},
    {"id": "topbanki", "name": "TopBanki", "kind": "banking_platform", "policy": "robots_checked", "status": "restricted", "review_parser": "generic_html", "supports_date_sort": False, "date_filter_year": 2026, "urls": ["https://topbanki.ru/"], "search_url": "https://topbanki.ru/search/?q={query}"},
    {"id": "vbr", "name": "Выберу.ру", "kind": "banking_platform", "policy": "robots_checked", "status": "restricted", "urls": ["https://www.vbr.ru/"], "search_url": "https://www.vbr.ru/search/?q={query}"},
    {"id": "yandex_maps", "name": "Яндекс Карты", "kind": "maps", "policy": "manual_only", "status": "manual_only", "urls": ["https://yandex.ru/maps/"]},
    {"id": "google_maps", "name": "Google Maps", "kind": "maps", "policy": "manual_only", "status": "manual_only", "urls": ["https://www.google.com/maps"]},
    {"id": "2gis", "name": "2GIS", "kind": "maps", "policy": "manual_only", "status": "manual_only", "urls": ["https://2gis.ru/"]},
    {"id": "vk", "name": "VK public pages", "kind": "social", "policy": "manual_only", "status": "manual_only", "urls": ["https://vk.com/"]},
    {"id": "telegram", "name": "Telegram public channels", "kind": "social", "policy": "manual_only", "status": "manual_only", "urls": ["https://t.me/"]},
    {"id": "dzen", "name": "Dzen", "kind": "social", "policy": "robots_checked", "status": "restricted", "urls": ["https://dzen.ru/"], "search_url": "https://dzen.ru/search?query={query}"},
    {"id": "vc_ru", "name": "VC.ru", "kind": "forum", "policy": "robots_checked", "status": "restricted", "urls": ["https://vc.ru/"]},
    {"id": "habr", "name": "Habr", "kind": "forum", "policy": "robots_checked", "status": "restricted", "urls": ["https://habr.com/"]},
    {"id": "smart_lab", "name": "Smart-Lab", "kind": "forum", "policy": "robots_checked", "status": "restricted", "urls": ["https://smart-lab.ru/"], "search_url": "https://smart-lab.ru/search/?q={query}"},
    {"id": "pikabu", "name": "Pikabu", "kind": "forum", "policy": "robots_checked", "status": "restricted", "urls": ["https://pikabu.ru/"], "search_url": "https://pikabu.ru/search?q={query}"},
    {"id": "reddit", "name": "Reddit", "kind": "forum", "policy": "robots_checked", "status": "restricted", "urls": ["https://www.reddit.com/"]},
    {"id": "youtube", "name": "YouTube", "kind": "video", "policy": "manual_only", "status": "manual_only", "urls": ["https://www.youtube.com/"]},
    {"id": "rutube", "name": "RuTube", "kind": "video", "policy": "robots_checked", "status": "restricted", "urls": ["https://rutube.ru/"], "search_url": "https://rutube.ru/search/?query={query}"},
    {"id": "app_store", "name": "App Store", "kind": "app_store", "policy": "manual_only", "status": "manual_only", "urls": ["https://apps.apple.com/"]},
    {"id": "google_play", "name": "Google Play", "kind": "app_store", "policy": "manual_only", "status": "manual_only", "urls": ["https://play.google.com/"]},
    {"id": "rustore", "name": "RuStore", "kind": "app_store", "policy": "manual_only", "status": "manual_only", "urls": ["https://www.rustore.ru/"]},
]


def product_ids() -> list:
    return list(PRODUCTS)


def get_product(product_id: str):
    return PRODUCTS.get(product_id)


def source_ids() -> list:
    return [src["id"] for src in FEEDBACK_SOURCES]


def get_source(source_id: str):
    for src in FEEDBACK_SOURCES:
        if src["id"] == source_id:
            return src
    return None


def aliases_for(product_id: str = None) -> list:
    if product_id:
        product = PRODUCTS.get(product_id)
        return list(product.get("aliases", [])) if product else []
    aliases = []
    for product in PRODUCTS.values():
        aliases.extend(product["aliases"])
    return aliases
