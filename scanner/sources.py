# -*- coding: utf-8 -*-
"""
Реестр источников: банки, тиры, экосистемные подписки и URL для скана.

Мультиисточниковая модель:
  - у каждого тира есть список источников (`sources`): официальный сайт банка,
    premiumbanking.info (ПБИ) и т.д. Каждый источник скачивается и парсится
    отдельно, данные сливаются в merge.py с фиксацией, откуда взята каждая цифра;
  - у банка могут быть `extra_sources` (Banki.ru, Sravni.ru, Bankiros) —
    страницы уровня банка, применяются ко всем его тирам как кросс-проверка;
  - внутри одного источника несколько URL — это fallback-цепочка (пробуем
    по порядку до первого успешного). Комплементарные страницы (например,
    отдельная страница вкладов) оформляются отдельным источником.

Приоритет источников при слиянии — см. SOURCE_META и scanner/merge.py.

`segment` — сегмент капитала по классификации premiumbanking.info
(0–3, 3–10, 10–25, 25–100 млн ₽): конфигурация раскладки сводной таблицы,
сверена с порогами входа на июль 2026.
"""

# Пауза между HTTP-запросами, сек (rate limiting)
REQUEST_PAUSE = 2.5

# Таймаут одного запроса, сек
REQUEST_TIMEOUT = 20

NOT_FOUND = "не найдено"

# Справочные поля: не участвуют в контуре «дозаполнить или отправить в
# ручную проверку» (не являются привилегиями)
REFERENCE_FIELDS = {"aggregator_value", "other_notes", "last_change_date"}

# Сегменты капитала в порядке отображения в сводной таблице
SEGMENTS = ["0–3 млн ₽", "3–10 млн ₽", "10–25 млн ₽", "25–100 млн ₽"]

# Источники данных. priority: меньше = приоритетнее при слиянии
# (curated — верифицированные вручную факты с ссылкой на первоисточник,
#  official — сайт банка как первоисточник цифр).
SOURCE_META = {
    "curated": {"name": "Ручная проверка (первоисточник)", "priority": 0},
    "official": {"name": "Официальный сайт банка", "priority": 1},
    "pbi": {"name": "premiumbanking.info", "priority": 2},
    "banki_ru": {"name": "Banki.ru", "priority": 3},
    "sravni_ru": {"name": "Sravni.ru", "priority": 4},
    "bankiros": {"name": "Bankiros.ru", "priority": 5},
    "frankrg": {"name": "Frank RG", "priority": 6},
}

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
                     "аэропорт", "mir pass", "every lounge"],
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
    "card_terms": {
        "label": "Карты (тип, лимиты переводов/снятия, выпуск)",
        "keywords": ["металлическ", "лимит на перевод", "переводы до",
                     "переводы без комиссии", "снятие наличн", "снять наличн",
                     "перевыпуск", "выпуск карты", "пластиков", "премиальная карта",
                     "лимитированн"],
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
        "keywords": ["авто", "каршеринг", "парковк", "водитель",
                     "помощь на дорог"],
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
        "label": "Оценка ценности пакета в год (ПБИ, справочно)",
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
LIFESTYLE_BANK_OVERLAP_JOBS = {
    "cashback": "кэшбэк на повседневные покупки (vs кэшбэк банковских пакетов)",
    "delivery": "доставка продуктов/товаров (vs возмещение Самоката и опций доставки)",
    "entertainment": "развлечения и контент (vs возмещения Афиши, консьерж-букинг)",
    "taxi": "такси и городской транспорт (vs компенсация такси в аэропорт/на ЖД)",
}


def _src(source_id, *urls):
    return {"source_id": source_id, "urls": list(urls)}


# Официальные страницы Сбера (проверены 2026-07-02)
_SBER_PREMIER_OFFICIAL = "https://www.sberbank.ru/ru/person/sb_premier_new"
_SBER_FIRST_OFFICIAL = "https://www.sberbank.ru/first"
_SBER_PREMIUM_OFFICIAL = "https://www.sberbank.ru/ru/person/premium"
_SBER_PREMIUM_VKLAD = "https://www.sberbank.ru/ru/person/premium/premium_vklad"
_SBER_FIRST_VKLADY = "https://www.sberbank.ru/ru/person/sb1/vklad/vse_vklady"
# Тарифы Премиальной СберКарты — первоисточник карточных лимитов всех уровней
_SBER_CARD_OFFICIAL = "https://www.sberbank.ru/ru/person/bank_cards/debit/sberkarta_premium"

# Структура тиров сверена с premiumbanking.info (июль 2026):
# у Сбера 6 уровней, у ВТБ 8 (Привилегия 1–4 + Прайм+ 5–8), у Т-Банка
# статусы Bronze/Silver/Gold/Diamond, у Озон Банка — линейка Ultra.
BANKS = [
    # ---------- НАША ЛИНЕЙКА ----------
    {
        "id": "sber",
        "name": "Сбер",
        "type": "our",
        "extra_sources": [
            _src("banki_ru", "https://www.banki.ru/banks/bank/sberbank/"),
            _src("sravni_ru",
                 "https://www.sravni.ru/enciklopediya/info/sberbank-premer-chto-ehto-takoe/"),
            _src("bankiros", "https://bankiros.ru/bank/sberbank"),
        ],
        "tiers": [
            {
                "tier_id": "sber_premier_1",
                "tier_name": "СберПремьер — уровень 1",
                "segment": "0–3 млн ₽",
                "sources": [
                    _src("official", _SBER_PREMIER_OFFICIAL),
                    _src("official", _SBER_PREMIUM_VKLAD),
                    _src("official", _SBER_CARD_OFFICIAL),
                    _src("pbi", "https://premiumbanking.info/sber/1"),
                ],
            },
            {
                "tier_id": "sber_premier_2",
                "tier_name": "СберПремьер — уровень 2",
                "segment": "3–10 млн ₽",
                "sources": [
                    _src("official", _SBER_PREMIER_OFFICIAL),
                    _src("official", _SBER_PREMIUM_VKLAD),
                    _src("official", _SBER_CARD_OFFICIAL),
                    _src("pbi", "https://premiumbanking.info/sber/2"),
                ],
            },
            {
                "tier_id": "sber_premier_3",
                "tier_name": "СберПремьер — уровень 3",
                "segment": "3–10 млн ₽",
                "sources": [
                    _src("official", _SBER_PREMIER_OFFICIAL),
                    _src("official", _SBER_PREMIUM_VKLAD),
                    _src("official", _SBER_CARD_OFFICIAL),
                    _src("pbi", "https://premiumbanking.info/sber/3"),
                ],
            },
            {
                "tier_id": "sber_first_4",
                "tier_name": "СберПервый — уровень 4",
                "segment": "10–25 млн ₽",
                "sources": [
                    _src("official", _SBER_FIRST_OFFICIAL),
                    _src("official", _SBER_FIRST_VKLADY),
                    _src("official", _SBER_CARD_OFFICIAL),
                    _src("pbi", "https://premiumbanking.info/sber/4"),
                ],
            },
            {
                "tier_id": "sber_first_5",
                "tier_name": "СберПервый — уровень 5",
                "segment": "25–100 млн ₽",
                "sources": [
                    _src("official", _SBER_FIRST_OFFICIAL),
                    _src("official", _SBER_FIRST_VKLADY),
                    _src("official", _SBER_CARD_OFFICIAL),
                    _src("pbi", "https://premiumbanking.info/sber/5"),
                ],
            },
            {
                "tier_id": "sber_private_6",
                "tier_name": "Sber Private Banking — уровень 6",
                "segment": "25–100 млн ₽",
                "sources": [
                    _src("official", "https://sberpb.ru/", _SBER_PREMIUM_OFFICIAL),
                    _src("official", _SBER_CARD_OFFICIAL),
                    _src("pbi", "https://premiumbanking.info/sber/6"),
                ],
            },
        ],
    },
    # ---------- ПРЯМЫЕ КОНКУРЕНТЫ ----------
    {
        "id": "tbank",
        "name": "Т-Банк",
        "type": "bank",
        "extra_sources": [
            _src("banki_ru", "https://www.banki.ru/banks/bank/tinkoff/",
                 "https://www.banki.ru/banks/bank/t-bank/"),
        ],
        "tiers": [
            {
                "tier_id": "tbank_bronze",
                "tier_name": "Premium Bronze",
                "segment": "0–3 млн ₽",
                "sources": [
                    _src("official", "https://www.tbank.ru/premium/"),
                    _src("pbi", "https://premiumbanking.info/tbank/1"),
                ],
            },
            {
                "tier_id": "tbank_silver",
                "tier_name": "Premium Silver",
                "segment": "3–10 млн ₽",
                "sources": [
                    _src("official", "https://www.tbank.ru/premium/"),
                    _src("pbi", "https://premiumbanking.info/tbank/2"),
                ],
            },
            {
                "tier_id": "tbank_gold",
                "tier_name": "Premium Gold",
                "segment": "3–10 млн ₽",
                "sources": [
                    _src("official", "https://www.tbank.ru/premium/"),
                    _src("pbi", "https://premiumbanking.info/tbank/3"),
                ],
            },
            {
                "tier_id": "tbank_diamond",
                "tier_name": "Private (Diamond)",
                "segment": "10–25 млн ₽",
                "sources": [
                    _src("official", "https://www.tbank.ru/private/"),
                    _src("pbi", "https://premiumbanking.info/tbank/4"),
                ],
            },
        ],
    },
    {
        "id": "alfa",
        "name": "Альфа-Банк",
        "type": "bank",
        "extra_sources": [
            _src("banki_ru", "https://www.banki.ru/banks/bank/alfabank/"),
            _src("bankiros", "https://bankiros.ru/bank/alfa-bank"),
        ],
        "tiers": [
            {
                "tier_id": "alfa_only_1",
                "tier_name": "Alfa Only — уровень 1",
                "segment": "0–3 млн ₽",
                "sources": [
                    _src("official", "https://alfabank.ru/everyday/alfa-only/"),
                    _src("pbi", "https://premiumbanking.info/alfabank/1"),
                ],
            },
            {
                "tier_id": "alfa_only_2",
                "tier_name": "Alfa Only — уровень 2",
                "segment": "3–10 млн ₽",
                "sources": [
                    _src("official", "https://alfabank.ru/everyday/alfa-only/"),
                    _src("pbi", "https://premiumbanking.info/alfabank/2"),
                ],
            },
            {
                "tier_id": "alfa_only_3",
                "tier_name": "Alfa Only — уровень 3",
                "segment": "3–10 млн ₽",
                "sources": [
                    _src("official", "https://alfabank.ru/everyday/alfa-only/"),
                    _src("pbi", "https://premiumbanking.info/alfabank/3"),
                ],
            },
            {
                "tier_id": "alfa_only_4",
                "tier_name": "Alfa Only — уровень 4",
                "segment": "10–25 млн ₽",
                "sources": [
                    _src("official", "https://alfabank.ru/everyday/alfa-only/"),
                    _src("pbi", "https://premiumbanking.info/alfabank/4"),
                ],
            },
            {
                "tier_id": "alfa_aclub",
                "tier_name": "A-Club (private)",
                "segment": "25–100 млн ₽",
                "sources": [
                    _src("official", "https://alfabank.ru/aclub/",
                         "https://www.aclub.ru/"),
                    _src("pbi", "https://premiumbanking.info/alfabank/5"),
                ],
            },
        ],
    },
    {
        "id": "vtb",
        "name": "ВТБ",
        "type": "bank",
        "extra_sources": [
            _src("banki_ru", "https://www.banki.ru/banks/bank/vtb/"),
            _src("bankiros", "https://bankiros.ru/bank/vtb"),
        ],
        "tiers": [
            {
                "tier_id": "vtb_privilege_1",
                "tier_name": "Привилегия — уровень 1",
                "segment": "0–3 млн ₽",
                "sources": [
                    _src("official", "https://www.vtb.ru/privilegia/"),
                    _src("pbi", "https://premiumbanking.info/vtb/1"),
                ],
            },
            {
                "tier_id": "vtb_privilege_2",
                "tier_name": "Привилегия — уровень 2",
                "segment": "0–3 млн ₽",
                "sources": [
                    _src("official", "https://www.vtb.ru/privilegia/"),
                    _src("pbi", "https://premiumbanking.info/vtb/2"),
                ],
            },
            {
                "tier_id": "vtb_privilege_3",
                "tier_name": "Привилегия — уровень 3",
                "segment": "3–10 млн ₽",
                "sources": [
                    _src("official", "https://www.vtb.ru/privilegia/"),
                    _src("pbi", "https://premiumbanking.info/vtb/3"),
                ],
            },
            {
                "tier_id": "vtb_privilege_4",
                "tier_name": "Привилегия — уровень 4",
                "segment": "10–25 млн ₽",
                "sources": [
                    _src("official", "https://www.vtb.ru/privilegia/"),
                    _src("pbi", "https://premiumbanking.info/vtb/4"),
                ],
            },
            {
                "tier_id": "vtb_prime_5",
                "tier_name": "Прайм+ — уровень 5",
                "segment": "3–10 млн ₽",
                "sources": [
                    _src("official", "https://private.vtb.ru/"),
                    _src("pbi", "https://premiumbanking.info/vtb/5"),
                ],
            },
            {
                "tier_id": "vtb_prime_6",
                "tier_name": "Прайм+ — уровень 6",
                "segment": "10–25 млн ₽",
                "sources": [
                    _src("official", "https://private.vtb.ru/"),
                    _src("pbi", "https://premiumbanking.info/vtb/6"),
                ],
            },
            {
                "tier_id": "vtb_prime_7",
                "tier_name": "Прайм+ — уровень 7",
                "segment": "25–100 млн ₽",
                "sources": [
                    _src("official", "https://private.vtb.ru/"),
                    _src("pbi", "https://premiumbanking.info/vtb/7"),
                ],
            },
            {
                "tier_id": "vtb_prime_8",
                "tier_name": "Прайм+ — уровень 8",
                "segment": "25–100 млн ₽",
                "sources": [
                    _src("official", "https://private.vtb.ru/"),
                    _src("pbi", "https://premiumbanking.info/vtb/8"),
                ],
            },
        ],
    },
    {
        "id": "gazprombank",
        "name": "Газпромбанк",
        "type": "bank",
        "extra_sources": [
            _src("banki_ru", "https://www.banki.ru/banks/bank/gazprombank/"),
            _src("bankiros", "https://bankiros.ru/bank/gazprombank"),
        ],
        "tiers": [
            {
                "tier_id": "gpb_premium_1",
                "tier_name": "Премиум — уровень 1",
                "segment": "0–3 млн ₽",
                "sources": [
                    _src("official", "https://www.gazprombank.ru/premium/"),
                    _src("pbi", "https://premiumbanking.info/gazprombank/1"),
                ],
            },
            {
                "tier_id": "gpb_premium_2",
                "tier_name": "Премиум — уровень 2",
                "segment": "3–10 млн ₽",
                "sources": [
                    _src("official", "https://www.gazprombank.ru/premium/"),
                    _src("pbi", "https://premiumbanking.info/gazprombank/2"),
                ],
            },
            {
                "tier_id": "gpb_premium_3",
                "tier_name": "Премиум — уровень 3",
                "segment": "10–25 млн ₽",
                "sources": [
                    _src("official", "https://www.gazprombank.ru/premium/"),
                    _src("pbi", "https://premiumbanking.info/gazprombank/3"),
                ],
            },
            {
                "tier_id": "gpb_private",
                "tier_name": "Private Banking",
                "segment": "25–100 млн ₽",
                "sources": [
                    _src("official", "https://www.gazprombank.ru/private/"),
                    _src("pbi", "https://premiumbanking.info/gazprombank/4"),
                ],
            },
        ],
    },
    {
        "id": "ozonbank",
        "name": "Озон Банк",
        "type": "bank",
        "extra_sources": [],
        "tiers": [
            {
                "tier_id": "ozonbank_ultra_bronze",
                "tier_name": "Ultra Bronze",
                "segment": "0–3 млн ₽",
                "sources": [
                    _src("official", "https://finance.ozon.ru/"),
                    _src("pbi", "https://premiumbanking.info/ozon/1"),
                ],
            },
            {
                "tier_id": "ozonbank_ultra_silver",
                "tier_name": "Ultra Silver",
                "segment": "3–10 млн ₽",
                "sources": [
                    _src("official", "https://finance.ozon.ru/"),
                    _src("pbi", "https://premiumbanking.info/ozon/2"),
                ],
            },
            {
                "tier_id": "ozonbank_ultra_gold",
                "tier_name": "Ultra Gold",
                "segment": "3–10 млн ₽",
                "sources": [
                    _src("official", "https://finance.ozon.ru/"),
                    _src("pbi", "https://premiumbanking.info/ozon/3"),
                ],
            },
            {
                "tier_id": "ozonbank_ultra_platinum",
                "tier_name": "Ultra Platinum",
                "segment": "10–25 млн ₽",
                "sources": [
                    _src("official", "https://finance.ozon.ru/"),
                    _src("pbi", "https://premiumbanking.info/ozon/4"),
                ],
            },
        ],
    },
    {
        "id": "raiffeisen",
        "name": "Райффайзен Банк",
        "type": "bank",
        "extra_sources": [
            _src("banki_ru", "https://www.banki.ru/banks/bank/raiffeisen/"),
        ],
        "tiers": [
            {
                "tier_id": "raif_premium_1",
                "tier_name": "Premium (за плату)",
                "segment": "0–3 млн ₽",
                "sources": [
                    _src("official", "https://www.raiffeisen.ru/premium/"),
                    _src("pbi", "https://premiumbanking.info/raiffeisen/1"),
                ],
            },
            {
                "tier_id": "raif_premium_2",
                "tier_name": "Premium (за траты)",
                "segment": "0–3 млн ₽",
                "sources": [
                    _src("official", "https://www.raiffeisen.ru/premium/"),
                    _src("pbi", "https://premiumbanking.info/raiffeisen/2"),
                ],
            },
            {
                "tier_id": "raif_premium_3",
                "tier_name": "Premium (за остаток)",
                "segment": "0–3 млн ₽",
                "sources": [
                    _src("official", "https://www.raiffeisen.ru/premium/"),
                    _src("pbi", "https://premiumbanking.info/raiffeisen/3"),
                ],
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
                "sources": [_src("official", "https://plus.yandex.ru/")],
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
                "sources": [
                    _src("official", "https://www.ozon.ru/premium/",
                         "https://www.ozon.ru/landing/premium/"),
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
                "sources": [
                    _src("official", "https://www.wildberries.ru/services/wb-club",
                         "https://www.wildberries.ru/"),
                ],
            },
        ],
    },
]

# Агрегаторы рыночного уровня — сканируются в --scan-all, raw-снимок для аудита
AGGREGATORS = [
    {
        "id": "premiumbanking_info",
        "name": "premiumbanking.info (обзорная)",
        "urls": ["https://premiumbanking.info/"],
    },
    {
        "id": "frankrg",
        "name": "Frank RG (рейтинги Premium/Private Banking)",
        "urls": ["https://frankrg.com/"],
    },
]


def tier_sources(bank: dict, tier: dict) -> list:
    """Все источники тира: собственные + банковские extra_sources."""
    return list(tier.get("sources", [])) + list(bank.get("extra_sources", []))


def get_bank(bank_id: str):
    for bank in BANKS:
        if bank["id"] == bank_id:
            return bank
    return None


def bank_ids():
    return [b["id"] for b in BANKS]
