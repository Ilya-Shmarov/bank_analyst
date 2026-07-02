# -*- coding: utf-8 -*-
"""
Реестр источников: банки, тиры, экосистемные подписки и URL для скана.

Добавление нового банка/подписки = добавление записи в BANKS.
Каждый тир может иметь несколько candidate-URL — fetch пробует по порядку
до первого успешного ответа (URL банков периодически меняются).

`segment` — сегмент капитала по классификации premiumbanking.info
(0–3, 3–10, 10–25, 25–100 млн ₽). Это конфигурация раскладки для сводной
таблицы, а не данные из источников — правьте под свою методологию.
"""

# Пауза между HTTP-запросами, сек (rate limiting)
REQUEST_PAUSE = 2.5

# Таймаут одного запроса, сек
REQUEST_TIMEOUT = 20

NOT_FOUND = "не найдено"

# Сегменты капитала в порядке отображения в сводной таблице
SEGMENTS = ["0–3 млн ₽", "3–10 млн ₽", "10–25 млн ₽", "25–100 млн ₽"]

# Поля, которые собираем по каждому банковскому тиру.
# keywords — маркеры для извлечения релевантных фрагментов текста страницы.
BANK_FIELDS = {
    "positioning": {
        "label": "Позиционирование (на кого рассчитан)",
        "keywords": ["для клиентов", "капитал", "состоятельн", "премиальн",
                     "privat", "уровень дохода", "статус"],
    },
    "entry_conditions": {
        "label": "Условия входа / поддержания уровня",
        "keywords": ["остаток", "оборот", "баланс", "бесплатное обслуживание",
                     "условия обслуживания", "суммарный", "среднемесячн"],
    },
    "service_cost": {
        "label": "Стоимость обслуживания",
        "keywords": ["стоимость обслуживания", "плата за обслуживание",
                     "руб/мес", "₽/мес", "рублей в месяц", "ежемесячная плата"],
    },
    "lounge_access": {
        "label": "Бизнес-залы (визиты, спутники)",
        "keywords": ["бизнес-зал", "бизнес зал", "lounge", "проход",
                     "аэропорт", "mir pass", "every lounge", "грабли"],
    },
    "concierge": {
        "label": "Консьерж-сервис",
        "keywords": ["консьерж", "concierge", "личный помощник", "ассистент"],
    },
    "cashback": {
        "label": "Кэшбэк (ставка, категории, механика)",
        "keywords": ["кэшбэк", "кешбэк", "cashback", "бонус", "баллы",
                     "категори", "спасибо"],
    },
    "deposits": {
        "label": "Спецусловия по вкладам / накопительным счетам",
        "keywords": ["вклад", "накопительн", "ставка", "процент годовых",
                     "% годовых", "надбавка"],
    },
    "insurance": {
        "label": "Страхование (мед., ВЗР)",
        "keywords": ["страхов", "взр", "путешеств", "медицинск", "телемедицин",
                     "чекап", "check-up"],
    },
    "auto": {
        "label": "Автоуслуги",
        "keywords": ["авто", "каршеринг", "парковк", "водитель"],
    },
    "taxi_restaurants": {
        "label": "Такси и рестораны (компенсации)",
        "keywords": ["такси", "ресторан", "трансфер", "кафе"],
    },
    "ecosystem": {
        "label": "Экосистемные привилегии (доставка, подписки)",
        "keywords": ["подписк", "доставк", "самокат", "афиша", "плюс",
                     "premium", "кино", "музыка", "экосистем"],
    },
    "addons": {
        "label": "Докупаемые опции и их цена",
        "keywords": ["опци", "докупить", "дополнительный пакет",
                     "подключить за", "стоимость опции"],
    },
    "aggregator_value": {
        "label": "Оценка ценности пакета в год (ПБИ)",
        "keywords": ["ценность"],
    },
    "other_notes": {
        "label": "Прочее (из источника)",
        "keywords": [],
    },
    "last_change_date": {
        "label": "Дата последнего изменения условий",
        "keywords": ["изменени", "вступает в силу", "обновлено", "действует с"],
    },
}

# Поля для экосистемных подписок (lifestyle-конкуренты)
LIFESTYLE_FIELDS = {
    "price": {
        "label": "Стоимость подписки",
        "keywords": ["₽ в месяц", "руб/мес", "рублей в месяц", "в год",
                     "стоимость", "цена подписки", "первые 30 дней", "бесплатно"],
    },
    "cashback": {
        "label": "Кэшбэк / баллы",
        "keywords": ["кэшбэк", "кешбэк", "баллы", "cashback", "возврат"],
    },
    "delivery": {
        "label": "Доставка",
        "keywords": ["доставк", "бесплатная доставка", "экспресс"],
    },
    "entertainment": {
        "label": "Развлечения (кино, музыка, контент)",
        "keywords": ["кино", "музыка", "кинопоиск", "сериал", "книги", "контент"],
    },
    "taxi": {
        "label": "Такси / транспорт",
        "keywords": ["такси", "драйв", "самокат", "транспорт"],
    },
}

# Джобы, по которым lifestyle-подписки пересекаются с банковскими привилегиями.
# Используется для колонки "Пересечения с банковскими привилегиями".
LIFESTYLE_BANK_OVERLAP_JOBS = {
    "cashback": "кэшбэк на повседневные покупки (vs кэшбэк банковских пакетов)",
    "delivery": "доставка продуктов/товаров (vs возмещение Самоката и опций доставки)",
    "entertainment": "развлечения и контент (vs возмещения Афиши, консьерж-букинг)",
    "taxi": "такси и городской транспорт (vs компенсация такси в аэропорт/на ЖД)",
}

# Структура тиров сверена с premiumbanking.info (июль 2026):
# у Сбера 6 уровней, у ВТБ 8 (Привилегия 1–4 + Прайм+ 5–8), у Т-Банка
# статусы Bronze/Silver/Gold/Diamond, у Озон Банка — линейка Ultra.
# Первый URL каждого тира — страница уровня на premiumbanking.info
# (приоритетный агрегатор по ТЗ), затем официальный сайт банка как сверка/fallback.
BANKS = [
    # ---------- НАША ЛИНЕЙКА ----------
    {
        "id": "sber",
        "name": "Сбер",
        "type": "our",
        "tiers": [
            {
                "tier_id": "sber_premier_1",
                "tier_name": "СберПремьер — уровень 1",
                "segment": "0–3 млн ₽",
                "urls": ["https://premiumbanking.info/sber/1",
                         "https://www.sberbank.ru/ru/person/sb_premier_new"],
            },
            {
                "tier_id": "sber_premier_2",
                "tier_name": "СберПремьер — уровень 2",
                "segment": "3–10 млн ₽",
                "urls": ["https://premiumbanking.info/sber/2",
                         "https://www.sberbank.ru/ru/person/sb_premier_new"],
            },
            {
                "tier_id": "sber_premier_3",
                "tier_name": "СберПремьер — уровень 3",
                "segment": "3–10 млн ₽",
                "urls": ["https://premiumbanking.info/sber/3",
                         "https://www.sberbank.ru/ru/person/sb_premier_new"],
            },
            {
                "tier_id": "sber_first_4",
                "tier_name": "СберПервый — уровень 4",
                "segment": "10–25 млн ₽",
                "urls": ["https://premiumbanking.info/sber/4",
                         "https://www.sberbank.ru/first"],
            },
            {
                "tier_id": "sber_first_5",
                "tier_name": "СберПервый — уровень 5",
                "segment": "25–100 млн ₽",
                "urls": ["https://premiumbanking.info/sber/5",
                         "https://www.sberbank.ru/first"],
            },
            {
                "tier_id": "sber_private_6",
                "tier_name": "Sber Private Banking — уровень 6",
                "segment": "25–100 млн ₽",
                "urls": ["https://premiumbanking.info/sber/6",
                         "https://www.sberbank.ru/ru/person/premium"],
            },
        ],
    },
    # ---------- ПРЯМЫЕ КОНКУРЕНТЫ ----------
    {
        "id": "tbank",
        "name": "Т-Банк",
        "type": "bank",
        "tiers": [
            {
                "tier_id": "tbank_bronze",
                "tier_name": "Premium Bronze",
                "segment": "0–3 млн ₽",
                "urls": ["https://premiumbanking.info/tbank/1",
                         "https://www.tbank.ru/premium/"],
            },
            {
                "tier_id": "tbank_silver",
                "tier_name": "Premium Silver",
                "segment": "3–10 млн ₽",
                "urls": ["https://premiumbanking.info/tbank/2",
                         "https://www.tbank.ru/premium/"],
            },
            {
                "tier_id": "tbank_gold",
                "tier_name": "Premium Gold",
                "segment": "3–10 млн ₽",
                "urls": ["https://premiumbanking.info/tbank/3",
                         "https://www.tbank.ru/premium/"],
            },
            {
                "tier_id": "tbank_diamond",
                "tier_name": "Private (Diamond)",
                "segment": "10–25 млн ₽",
                "urls": ["https://premiumbanking.info/tbank/4",
                         "https://www.tbank.ru/private/"],
            },
        ],
    },
    {
        "id": "alfa",
        "name": "Альфа-Банк",
        "type": "bank",
        "tiers": [
            {
                "tier_id": "alfa_only_1",
                "tier_name": "Alfa Only — уровень 1",
                "segment": "0–3 млн ₽",
                "urls": ["https://premiumbanking.info/alfabank/1",
                         "https://alfabank.ru/everyday/alfa-only/"],
            },
            {
                "tier_id": "alfa_only_2",
                "tier_name": "Alfa Only — уровень 2",
                "segment": "3–10 млн ₽",
                "urls": ["https://premiumbanking.info/alfabank/2",
                         "https://alfabank.ru/everyday/alfa-only/"],
            },
            {
                "tier_id": "alfa_only_3",
                "tier_name": "Alfa Only — уровень 3",
                "segment": "3–10 млн ₽",
                "urls": ["https://premiumbanking.info/alfabank/3",
                         "https://alfabank.ru/everyday/alfa-only/"],
            },
            {
                "tier_id": "alfa_only_4",
                "tier_name": "Alfa Only — уровень 4",
                "segment": "10–25 млн ₽",
                "urls": ["https://premiumbanking.info/alfabank/4",
                         "https://alfabank.ru/everyday/alfa-only/"],
            },
            {
                "tier_id": "alfa_aclub",
                "tier_name": "A-Club (private)",
                "segment": "25–100 млн ₽",
                "urls": ["https://alfabank.ru/aclub/",
                         "https://www.aclub.ru/"],
            },
        ],
    },
    {
        "id": "vtb",
        "name": "ВТБ",
        "type": "bank",
        "tiers": [
            {
                "tier_id": "vtb_privilege_1",
                "tier_name": "Привилегия — уровень 1",
                "segment": "0–3 млн ₽",
                "urls": ["https://premiumbanking.info/vtb/1",
                         "https://www.vtb.ru/privilegia/"],
            },
            {
                "tier_id": "vtb_privilege_2",
                "tier_name": "Привилегия — уровень 2",
                "segment": "0–3 млн ₽",
                "urls": ["https://premiumbanking.info/vtb/2",
                         "https://www.vtb.ru/privilegia/"],
            },
            {
                "tier_id": "vtb_privilege_3",
                "tier_name": "Привилегия — уровень 3",
                "segment": "3–10 млн ₽",
                "urls": ["https://premiumbanking.info/vtb/3",
                         "https://www.vtb.ru/privilegia/"],
            },
            {
                "tier_id": "vtb_privilege_4",
                "tier_name": "Привилегия — уровень 4",
                "segment": "10–25 млн ₽",
                "urls": ["https://premiumbanking.info/vtb/4",
                         "https://www.vtb.ru/privilegia/"],
            },
            {
                "tier_id": "vtb_prime_5",
                "tier_name": "Прайм+ — уровень 5",
                "segment": "3–10 млн ₽",
                "urls": ["https://premiumbanking.info/vtb/5",
                         "https://private.vtb.ru/"],
            },
            {
                "tier_id": "vtb_prime_6",
                "tier_name": "Прайм+ — уровень 6",
                "segment": "10–25 млн ₽",
                "urls": ["https://premiumbanking.info/vtb/6",
                         "https://private.vtb.ru/"],
            },
            {
                "tier_id": "vtb_prime_7",
                "tier_name": "Прайм+ — уровень 7",
                "segment": "25–100 млн ₽",
                "urls": ["https://premiumbanking.info/vtb/7",
                         "https://private.vtb.ru/"],
            },
            {
                "tier_id": "vtb_prime_8",
                "tier_name": "Прайм+ — уровень 8",
                "segment": "25–100 млн ₽",
                "urls": ["https://premiumbanking.info/vtb/8",
                         "https://private.vtb.ru/"],
            },
        ],
    },
    {
        "id": "gazprombank",
        "name": "Газпромбанк",
        "type": "bank",
        "tiers": [
            {
                "tier_id": "gpb_premium_1",
                "tier_name": "Премиум — уровень 1",
                "segment": "0–3 млн ₽",
                "urls": ["https://premiumbanking.info/gazprombank/1",
                         "https://www.gazprombank.ru/premium/"],
            },
            {
                "tier_id": "gpb_premium_2",
                "tier_name": "Премиум — уровень 2",
                "segment": "3–10 млн ₽",
                "urls": ["https://premiumbanking.info/gazprombank/2",
                         "https://www.gazprombank.ru/premium/"],
            },
            {
                "tier_id": "gpb_premium_3",
                "tier_name": "Премиум — уровень 3",
                "segment": "10–25 млн ₽",
                "urls": ["https://premiumbanking.info/gazprombank/3",
                         "https://www.gazprombank.ru/premium/"],
            },
            {
                "tier_id": "gpb_private",
                "tier_name": "Private Banking",
                "segment": "25–100 млн ₽",
                "urls": ["https://premiumbanking.info/gazprombank/4",
                         "https://www.gazprombank.ru/private/"],
            },
        ],
    },
    {
        "id": "ozonbank",
        "name": "Озон Банк",
        "type": "bank",
        "tiers": [
            {
                "tier_id": "ozonbank_ultra_bronze",
                "tier_name": "Ultra Bronze",
                "segment": "0–3 млн ₽",
                "urls": ["https://premiumbanking.info/ozon/1",
                         "https://finance.ozon.ru/"],
            },
            {
                "tier_id": "ozonbank_ultra_silver",
                "tier_name": "Ultra Silver",
                "segment": "3–10 млн ₽",
                "urls": ["https://premiumbanking.info/ozon/2",
                         "https://finance.ozon.ru/"],
            },
            {
                "tier_id": "ozonbank_ultra_gold",
                "tier_name": "Ultra Gold",
                "segment": "3–10 млн ₽",
                "urls": ["https://premiumbanking.info/ozon/3",
                         "https://finance.ozon.ru/"],
            },
            {
                "tier_id": "ozonbank_ultra_platinum",
                "tier_name": "Ultra Platinum",
                "segment": "10–25 млн ₽",
                "urls": ["https://premiumbanking.info/ozon/4",
                         "https://finance.ozon.ru/"],
            },
        ],
    },
    {
        "id": "raiffeisen",
        "name": "Райффайзен Банк",
        "type": "bank",
        "tiers": [
            {
                "tier_id": "raif_premium_1",
                "tier_name": "Premium (за плату)",
                "segment": "0–3 млн ₽",
                "urls": ["https://premiumbanking.info/raiffeisen/1",
                         "https://www.raiffeisen.ru/premium/"],
            },
            {
                "tier_id": "raif_premium_2",
                "tier_name": "Premium (за траты)",
                "segment": "0–3 млн ₽",
                "urls": ["https://premiumbanking.info/raiffeisen/2",
                         "https://www.raiffeisen.ru/premium/"],
            },
            {
                "tier_id": "raif_premium_3",
                "tier_name": "Premium (за остаток)",
                "segment": "0–3 млн ₽",
                "urls": ["https://premiumbanking.info/raiffeisen/3",
                         "https://www.raiffeisen.ru/premium/"],
            },
        ],
    },
    # ---------- LIFESTYLE-КОНКУРЕНТЫ ----------
    {
        "id": "yandex_plus",
        "name": "Яндекс Плюс",
        "type": "lifestyle",
        "tiers": [
            {
                "tier_id": "yandex_plus_main",
                "tier_name": "Яндекс Плюс",
                "segment": None,
                "urls": ["https://plus.yandex.ru/"],
            },
        ],
    },
    {
        "id": "ozon_premium",
        "name": "Ozon Premium",
        "type": "lifestyle",
        "tiers": [
            {
                "tier_id": "ozon_premium_main",
                "tier_name": "Ozon Premium",
                "segment": None,
                "urls": [
                    "https://www.ozon.ru/premium/",
                    "https://www.ozon.ru/landing/premium/",
                ],
            },
        ],
    },
    {
        "id": "wildberries",
        "name": "Wildberries (Клуб покупателей)",
        "type": "lifestyle",
        "tiers": [
            {
                "tier_id": "wb_club",
                "tier_name": "WB Клуб",
                "segment": None,
                "urls": [
                    "https://www.wildberries.ru/services/wb-club",
                    "https://www.wildberries.ru/",
                ],
            },
        ],
    },
]

# Агрегаторы — сканируются отдельно, результат идёт в метаданные и raw-архив
# (структурированный парсинг агрегаторов подключается отдельным парсером).
AGGREGATORS = [
    {
        "id": "premiumbanking_info",
        "name": "premiumbanking.info (приоритетный агрегатор)",
        "urls": ["https://premiumbanking.info/"],
    },
    {
        "id": "frankrg",
        "name": "Frank RG",
        "urls": ["https://frankrg.com/"],
    },
]


def get_bank(bank_id: str):
    for bank in BANKS:
        if bank["id"] == bank_id:
            return bank
    return None


def bank_ids():
    return [b["id"] for b in BANKS]
