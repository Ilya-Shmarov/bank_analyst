# -*- coding: utf-8 -*-
"""
Верифицированные вручную факты (source_id = "curated").

Это НЕ разовый хардкод в ячейках отчёта: записи применяются при каждом
скане как источник с наивысшим приоритетом, каждая несёт ссылку на
первоисточник и дату проверки (`date_checked`). Если запись устарела —
обновите значение и дату или удалите её, чтобы поле снова заполнялось
автоматическим парсингом.

Правила ведения:
  - значение — факт с точными цифрами и формулировками первоисточника;
  - source_url — официальная страница (или страница ПБИ, если официальный
    сайт не публикует деталь);
  - date_checked — дата последней сверки с первоисточником;
  - note — контекст: что проверено, что не подтвердилось.

Записи со старым date_checked (> STALE_DAYS) помечаются в отчёте
«проверить актуальность».
"""

STALE_DAYS = 90

_SBER_PREMIER = "https://www.sberbank.ru/ru/person/sb_premier_new"
_SBER_FIRST = "https://www.sberbank.ru/first"
_SBER_VKLAD = "https://www.sberbank.ru/ru/person/premium/premium_vklad"
_SBER_FIRST_VKLADY = "https://www.sberbank.ru/ru/person/sb1/vklad/vse_vklady"
_SBER_CARD = "https://www.sberbank.ru/ru/person/bank_cards/debit/sberkarta_premium"
_PBI_SBER = "https://premiumbanking.info/sber"

_CHECKED = "2026-07-02"

# ---------- Карты (Премиальная СберКарта, тарифы одной страницы для всех уровней)
_PREMIER_CARD = {
    "value": ("Премиальная СберКарта: пластик или металл (металлический носитель "
              "доступен всем премиальным уровням). Переводы без комиссии до "
              "35 млн ₽ в сутки; снятие наличных до 1 млн ₽ в день. Стоимость "
              "выпуска металлической карты на странице тарифов не указана"),
    "source_url": _SBER_CARD,
    "date_checked": _CHECKED,
    "note": "Лимит «до 35 млн ₽/сутки» из вводной подтверждён (Премьер и Первый)",
}

_FIRST_CARD = {
    "value": ("Премиальная СберКарта: пластик или металл. Переводы без комиссии "
              "до 35 млн ₽ в сутки; снятие наличных до 2 млн ₽ в день"),
    "source_url": _SBER_CARD,
    "date_checked": _CHECKED,
    "note": ("Вторичные источники (banki.ru) упоминали выпуск металлической "
             "карты СберПервый за 7 500 ₽ — на официальной странице цена "
             "не опубликована, требует сверки в тарифах PDF"),
}

_PRIVATE_CARD = {
    "value": ("Премиальная СберКарта уровня Private: переводы без комиссии до "
              "50 млн ₽ в сутки; снятие наличных до 3 млн ₽ в день; "
              "лимитированная серия металлических карт (чёрные и белые) — "
              "только для уровня 6 / Sber Private Banking"),
    "source_url": _SBER_CARD,
    "date_checked": _CHECKED,
    "note": "Лимиты Private выше вводной: 50 млн ₽/сутки, а не 35",
}

# Консьерж на СберПремьер отсутствует — общая запись для уровней 1–3
_PREMIER_CONCIERGE = {
    "value": ("Нет — консьерж-сервис не входит в СберПремьер. На уровнях 1–3 "
              "только личный менеджер и выделенная линия 900; набор привилегий — "
              "опции «Бизнес-залы», «Такси и рестораны», «Здоровье», «Самокат», "
              "«Питомцы», «Авто» + СберПрайм"),
    "source_url": _SBER_PREMIER,
    "date_checked": _CHECKED,
    "note": "Сверено с официальной страницей и ПБИ /sber/1–3",
}

_PREMIER_DEPOSITS = {
    "value": ("Вклад «Премиум» до 13,8% годовых (базовая ставка + надбавки: "
              "до +1,3 п.п. за уровень премиального обслуживания, до +0,5 п.п. "
              "за инвестиции, +0,5 п.п. за покупки от 30 тыс ₽/мес для уровней "
              "1–3; мин. сумма 100 тыс ₽, сроки 1 мес–3 года). Накопительный "
              "счёт «Премиум» до 13%. Ставки на дату проверки, меняются вслед "
              "за ключевой ставкой ЦБ"),
    "source_url": _SBER_VKLAD,
    "date_checked": _CHECKED,
    "note": "Максимум 13,8% — новые деньги, 3–4 мес, проценты в конце срока",
}

_FIRST_DEPOSITS = {
    "value": ("Линейка премиальных вкладов: СберВклад Премиум, «Лучший % Премиум», "
              "«Управляй Премиум», накопительный счёт «Премиум». Позиционирование "
              "«самые высокие ставки в СберБанке»; конкретные надбавки для уровней "
              "4–5 публикуются в PDF-тарифах, на продуктовой странице цифр нет. "
              "Ориентир — вклад «Премиум» до 13,8% (доступен и для СберПервого)"),
    "source_url": _SBER_FIRST_VKLADY,
    "date_checked": _CHECKED,
    "note": "Ставки меняются вслед за КС ЦБ — сверять на дату скана",
}

CURATED_FACTS = {
    # ---------- СберПремьер (уровни 1–3) ----------
    "sber_premier_1": {
        "concierge": _PREMIER_CONCIERGE,
        "cashback": {
            "value": ("Кэшбэк до 10% бонусами СберСпасибо в 5 категориях на выбор "
                      "ежемесячно, суммарный лимит 20 000 бонусов за расчётный "
                      "период. Повышенный курс обмена бонусов на уровне 1 не указан"),
            "source_url": _SBER_PREMIER,
            "date_checked": _CHECKED,
            "note": ("«10% по 6 категориям» из вводной относится к уровню Private "
                     "(6 категорий, безлимит), у Премьера/Первого — 5 категорий"),
        },
        "card_terms": _PREMIER_CARD,
        "deposits": _PREMIER_DEPOSITS,
    },
    "sber_premier_2": {
        "concierge": _PREMIER_CONCIERGE,
        "cashback": {
            "value": ("Кэшбэк до 10% бонусами СберСпасибо в 5 категориях на выбор "
                      "ежемесячно, лимит 20 000 бонусов за расчётный период. "
                      "Повышенный курс обмена бонусов на уровне 2 не указан"),
            "source_url": _SBER_PREMIER,
            "date_checked": _CHECKED,
            "note": "5 категорий (6 — только на Private)",
        },
        "card_terms": _PREMIER_CARD,
        "deposits": _PREMIER_DEPOSITS,
    },
    "sber_premier_3": {
        "concierge": _PREMIER_CONCIERGE,
        "cashback": {
            "value": ("Кэшбэк до 10% бонусами СберСпасибо в 5 категориях на выбор "
                      "ежемесячно, лимит 20 000 бонусов за расчётный период. "
                      "Обмен бонусов по повышенному курсу: 10 бонусов = 7 ₽, "
                      "лимит 12 500 бонусов/мес"),
            "source_url": f"{_PBI_SBER}/3",
            "date_checked": _CHECKED,
            "note": "Курс обмена — по ПБИ; ставка/категории — sberbank.ru",
        },
        "card_terms": _PREMIER_CARD,
        "deposits": _PREMIER_DEPOSITS,
    },
    # ---------- СберПервый (уровни 4–5) ----------
    "sber_first_4": {
        "concierge": {
            "value": ("Есть — консьерж Aspire («поддержка профессионального "
                      "ассистента во всех сферах жизни»). Также: безлимитные "
                      "бизнес-залы, компенсация БЗ за границей 3 тыс ₽/чел, "
                      "СберПрайм+ (Okko Премиум с Amediateka)"),
            "source_url": _SBER_FIRST,
            "date_checked": _CHECKED,
            "note": "Название Aspire — по ПБИ /sber/4; официальный сайт "
                    "описывает сервис без бренда",
        },
        "cashback": {
            "value": ("Кэшбэк до 10% бонусами Спасибо в 5 категориях ежемесячно. "
                      "Обмен бонусов по повышенному курсу 1 бонус = 0,8 ₽ "
                      "(10 Б = 8 ₽), до 10 000 ₽/мес (лимит 12 500 Б/мес)"),
            "source_url": _SBER_FIRST,
            "date_checked": _CHECKED,
            "note": "Курс подтверждён двумя источниками: sberbank.ru/first и ПБИ",
        },
        "card_terms": _FIRST_CARD,
        "deposits": _FIRST_DEPOSITS,
    },
    "sber_first_5": {
        "concierge": {
            "value": "Есть — консьерж Aspire (как на уровне 4)",
            "source_url": _SBER_FIRST,
            "date_checked": _CHECKED,
            "note": "См. sber_first_4",
        },
        "cashback": {
            "value": ("Кэшбэк до 10% бонусами Спасибо в 5 категориях. Обмен "
                      "10 бонусов = 8 ₽, лимит 12 500 Б/мес"),
            "source_url": _SBER_FIRST,
            "date_checked": _CHECKED,
            "note": "",
        },
        "card_terms": _FIRST_CARD,
        "deposits": _FIRST_DEPOSITS,
    },
    # ---------- Sber Private Banking (уровень 6) ----------
    "sber_private_6": {
        "concierge": {
            "value": ("Есть — консьерж Pb Service (отдельный private-консьерж, "
                      "НЕ Aspire). Дополнительно: 3 консультации в год СберПраво, "
                      "Сбер Мобайл (звонки + 5 ГБ/мес), бизнес-зал Сбер в SVO "
                      "без ограничений"),
            "source_url": f"{_PBI_SBER}/6",
            "date_checked": _CHECKED,
            "note": ("Вопрос из вводной «тот же Aspire или отдельный?» — отдельный: "
                     "Pb Service. sberpb.ru — JS-сайт, детально мандат сервиса "
                     "на нём не опубликован"),
        },
        "cashback": {
            "value": ("Кэшбэк до 10% бонусами в 6 категориях на выбор, бонусы "
                      "без лимита (безлимитное начисление — отличие уровня "
                      "Private). Обмен бонусов Спасибо по повышенному курсу: "
                      "10 бонусов = 8 ₽, лимит обмена 12 500 Б/мес"),
            "source_url": _SBER_CARD,
            "date_checked": _CHECKED,
            "note": ("Это источник цифры «10% по 6 категориям» из вводной — "
                     "она относится именно к Private, не к Премьеру/Первому. "
                     "Курс обмена — по ПБИ /sber/6"),
        },
        "card_terms": _PRIVATE_CARD,
        "deposits": _FIRST_DEPOSITS,
    },
}


# ============================================================================
# КОНКУРЕНТЫ — целевое дозаполнение пустых полей (2026-07-02).
# Значение «— (…)» = услуга отсутствует по официальным условиям тира
# (НЕ путать с «не найдено» — то уходит в лист «Требует ручной проверки»).
# ============================================================================

def _fact(value, url, note=""):
    return {"value": value, "source_url": url,
            "date_checked": _CHECKED, "note": note}


def _free_on_conditions(pbi_url):
    return _fact("0 ₽ — бесплатно при выполнении условий уровня (остаток/траты/"
                 "акции определяют сам уровень, отдельная плата не предусмотрена)",
                 pbi_url, "Выведено из условий входа уровня (ПБИ)")


# ---------- Т-Банк ----------
_TBANK_PREMIUM = "https://www.tbank.ru/tinkoff-premium/"
_TBANK_SERVICES = "https://www.tbank.ru/bank/help/general/premium/services/"
_TBANK_CARD = ("https://www.tbank.ru/tinkoff-premium/cards/debit-cards/"
               "tinkoff-black-premium/")

_TBANK_SHARED = {
    "concierge": _fact(
        "Есть — круглосуточная консьерж-служба с личным ассистентом "
        "(бронирования, билеты, подбор специалистов) + премиальная "
        "поддержка выделенной командой",
        _TBANK_PREMIUM,
        "Ложное «нет» из автопарсинга ПБИ исправлено по официальному сайту"),
    "cashback": _fact(
        "Базовая программа кэшбэка Т-Банка (1–30% по категориям и партнёрам); "
        "с Premium лимит кэшбэка повышен до 60 000 ₽/мес по картам Black Premium",
        _TBANK_PREMIUM,
        "Лимит без Premium — 30 000 ₽/мес"),
    "deposits": _fact(
        "Повышенная доходность по вкладам для клиентов Premium "
        "(маркетинговое «до 15%» на странице Premium; базовая линейка вкладов "
        "до 12% на дату проверки). Точная надбавка — в тарифах",
        _TBANK_PREMIUM,
        "Ставки меняются вслед за КС ЦБ"),
    "card_terms": _fact(
        "Металлическая дебетовая карта Black Premium для клиентов Premium. "
        "Снятие наличных: в банкоматах Т-Банка без ограничений, в чужих — "
        "до 500 000 ₽ за расчётный период без комиссии",
        _TBANK_CARD, ""),
    "auto": _fact(
        "— (автоуслуги не входят в состав сервиса Premium по официальному "
        "перечню услуг)",
        _TBANK_SERVICES, "Отсутствие по официальным условиям"),
    "addons": _fact(
        "— (докупаемых опций нет: Premium — единая подписка, уровни статуса "
        "определяются остатком/активами)",
        _TBANK_PREMIUM, "Отсутствие по официальным условиям"),
}

# ---------- ВТБ (Привилегия, уровни 1–4) ----------
_VTB_SERVICES = "https://www.vtb.ru/privilegia/premialnye-servisy/"
_VTB_CARD = ("https://www.vtb.ru/privilegia/karty/debetovye/"
             "privilegiya-mir-supreme/")
_VTB_MAIN = "https://www.vtb.ru/privilegia/"

_VTB_PRIVILEGE_SHARED = {
    "concierge": _fact(
        "Есть — круглосуточный консьерж-сервис, бесплатно для всех клиентов "
        "«Привилегии»: юридическая, деловая и медицинская поддержка, "
        "путешествия/досуг, детский консьерж",
        _VTB_SERVICES, ""),
    "cashback": _fact(
        "Кэшбэк 1–15% рублями в 3 категориях (4 для зарплатных клиентов) "
        "на выбор из 9; по отдельным категориям лимиты "
        "(например, «Такси» — до 1 000 ₽/мес)",
        _VTB_CARD, "Начисляется рублями, не мультибонусами"),
    "deposits": _fact(
        "Накопительный ВТБ-Счёт до 13,75% годовых (повышенная ставка за "
        "покупки по карте); опция «Сбережения»: надбавка +1–3 п.п. к ставке "
        "в зависимости от оборота по карте. Ставки на дату проверки",
        _VTB_MAIN, ""),
    "card_terms": _fact(
        "Карта «Привилегия Mir Supreme» (есть цифровая версия). Снятие без "
        "комиссии в банкоматах ВТБ и партнёров группы: до 350 000 ₽/день, "
        "до 2 млн ₽/мес",
        _VTB_CARD, ""),
    "auto": _fact(
        "Есть — «Помощь на дорогах»: эвакуатор, техническая и юридическая "
        "поддержка (для поездок на личном автомобиле)",
        _VTB_SERVICES, ""),
}

# ---------- Озон Банк (Ultra) ----------
_OZON_PRODUCTS = "https://finance.ozon.ru/products"
_OZON_HELP = "https://help-bank.ozon.ru/individuals/bonuses-and-promotions"

_OZONBANK_SHARED = {
    "cashback": _fact(
        "Кэшбэк рублями: общий лимит для Ultra до 50 000 ₽/мес, до 10 "
        "категорий на выбор ежемесячно (лимит по одной категории 10 000 "
        "₽/мес), «1% на всё» в рамках общего лимита. Выплата реальными "
        "рублями (можно снять/перевести)",
        _OZON_HELP, ""),
    "card_terms": _fact(
        "Карта Ozon: для Ultra повышенный лимит на снятие наличных без "
        "комиссии в любых банкоматах и увеличенный лимит по счёту "
        "(конкретные суммы по уровням — в тарифах)",
        _OZON_PRODUCTS, ""),
    "auto": _fact(
        "— (автоуслуги не входят в состав Ultra по официальному описанию "
        "программы: менеджер, поддержка, страховка, бизнес-залы, "
        "Ozon Premium, кэшбэк, лимиты)",
        _OZON_PRODUCTS, "Отсутствие по официальным условиям"),
    "concierge": _fact(
        "— (консьерж-сервис не заявлен в составе Ultra; вместо него — "
        "персональный менеджер и круглосуточная поддержка)",
        _OZON_PRODUCTS, "Отсутствие по официальному составу программы"),
    "addons": _fact(
        "— (докупаемых опций нет: уровни Ultra определяются остатком, "
        "подписка Ozon Premium уже включена)",
        _OZON_PRODUCTS, "Отсутствие по официальным условиям"),
}

# ---------- Газпромбанк ----------
_GPB_BONUS = "https://www.gazprombank.ru/premium/gazprom-bonus/"

# ---------- Альфа-Банк ----------
_ALFA_ONLY = "https://alfabank.ru/everyday/alfa-only/"
_ALFA_CONCIERGE = "https://alfabank.ru/everyday/package/premium/konserzh-servis/"
_PBI_ACLUB = "https://premiumbanking.info/alfabank/5"

_ALFA_CONCIERGE_FACT = _fact(
    "Есть — консьерж-сервис для клиентов Alfa Only (официальная страница "
    "«Консьерж-сервис — премиум-услуги для клиентов Alfa Only»)",
    _ALFA_CONCIERGE,
    "Ложное «нет» из автопарсинга ПБИ исправлено по официальному сайту")

_ALFA_ADDONS_ABSENT = _fact(
    "— (докупаемых опций нет: набор привилегий Alfa Only фиксированный — "
    "Lounge, металлическая карта, партнёрские программы, премиальный вклад, "
    "привилегии в ресторанах)",
    _ALFA_ONLY, "Отсутствие по официальному составу пакета")

# ---------- Райффайзен ----------
_RAIF_PREMIUM = "https://www.raiffeisen.ru/premium/"

_RAIF_ADDONS_ABSENT = _fact(
    "— (докупаемых опций нет: Premium — фиксированный пакет, различаются "
    "только способы бесплатного входа: плата/траты/остаток)",
    _RAIF_PREMIUM, "Отсутствие по официальным условиям")

# ---------- Lifestyle ----------
_OZON_PREMIUM_DOCS = ("https://docs.ozon.ru/common/pravila-prodayoi-i-rekvizity/"
                      "usloviya-podpiski-na-ozon-premium/")
_WB_CLUB_NEWS = "https://oborot.ru/news/chto-takoe-wb-klub-razbiraemsya-chto-daet-podpiska-za-199-rublej-v-mesyac-pokupatelyam-wildberries-i222045.html"
_YANDEX_PLUS_SUPPORT = "https://yandex.ru/support/plus-ru/ru/cashback"

_COMPETITOR_FACTS = {
    # ----- Т-Банк -----
    "tbank_bronze": dict(_TBANK_SHARED),
    "tbank_silver": {**_TBANK_SHARED,
                     "service_cost": _free_on_conditions(
                         "https://premiumbanking.info/tbank/2")},
    "tbank_gold": {**_TBANK_SHARED,
                   "service_cost": _free_on_conditions(
                       "https://premiumbanking.info/tbank/3")},
    "tbank_diamond": {**_TBANK_SHARED,
                      "service_cost": _free_on_conditions(
                          "https://premiumbanking.info/tbank/4")},
    # ----- ВТБ: Привилегия 1–4 (Прайм+ 5–8 не публикует детали — ручная проверка)
    "vtb_privilege_1": {**_VTB_PRIVILEGE_SHARED,
                        "addons": _fact(
                            "— (механика выбора привилегий на уровне 1 не "
                            "заявлена на странице уровня; появляется с "
                            "уровней выше)",
                            "https://premiumbanking.info/vtb/1",
                            "Отсутствие по структуре условий уровня")},
    "vtb_privilege_2": {**_VTB_PRIVILEGE_SHARED,
                        "service_cost": _free_on_conditions(
                            "https://premiumbanking.info/vtb/2")},
    "vtb_privilege_3": {**_VTB_PRIVILEGE_SHARED,
                        "service_cost": _free_on_conditions(
                            "https://premiumbanking.info/vtb/3")},
    "vtb_privilege_4": {**_VTB_PRIVILEGE_SHARED,
                        "service_cost": _free_on_conditions(
                            "https://premiumbanking.info/vtb/4")},
    "vtb_prime_6": {"service_cost": _free_on_conditions(
        "https://premiumbanking.info/vtb/6")},
    "vtb_prime_7": {"service_cost": _free_on_conditions(
        "https://premiumbanking.info/vtb/7")},
    "vtb_prime_8": {"service_cost": _free_on_conditions(
        "https://premiumbanking.info/vtb/8")},
    # ----- Озон Банк -----
    "ozonbank_ultra_bronze": dict(_OZONBANK_SHARED),
    "ozonbank_ultra_silver": {**_OZONBANK_SHARED,
                              "service_cost": _free_on_conditions(
                                  "https://premiumbanking.info/ozon/2")},
    "ozonbank_ultra_gold": {**_OZONBANK_SHARED,
                            "service_cost": _free_on_conditions(
                                "https://premiumbanking.info/ozon/3")},
    "ozonbank_ultra_platinum": {**_OZONBANK_SHARED,
                                "service_cost": _free_on_conditions(
                                    "https://premiumbanking.info/ozon/4")},
    # ----- Газпромбанк Private -----
    "gpb_private": {
        "service_cost": _free_on_conditions(
            "https://premiumbanking.info/gazprombank/4"),
        "cashback": _fact(
            "Программа лояльности «Умный кэшбэк» (Газпром Бонус «Премиум»): "
            "до 15% + до 7% от ПС «Мир» в ресторанах, суммарно до 22%, "
            "лимит 40 000 ₽/мес",
            _GPB_BONUS,
            "Детализация именно для уровня Private не публикуется — "
            "указана премиальная версия программы банка"),
    },
    # ----- Альфа-Банк -----
    "alfa_only_1": {"addons": _ALFA_ADDONS_ABSENT,
                    "concierge": _ALFA_CONCIERGE_FACT},
    "alfa_only_2": {"addons": _ALFA_ADDONS_ABSENT,
                    "concierge": _ALFA_CONCIERGE_FACT,
                    "service_cost": _free_on_conditions(
                        "https://premiumbanking.info/alfabank/2")},
    "alfa_only_3": {"addons": _ALFA_ADDONS_ABSENT,
                    "concierge": _ALFA_CONCIERGE_FACT,
                    "service_cost": _free_on_conditions(
                        "https://premiumbanking.info/alfabank/3")},
    "alfa_only_4": {"addons": _ALFA_ADDONS_ABSENT,
                    "concierge": _ALFA_CONCIERGE_FACT,
                    "service_cost": _free_on_conditions(
                        "https://premiumbanking.info/alfabank/4")},
    "alfa_aclub": {
        "entry_conditions": _fact(
            "60 млн ₽ на счетах для Москвы | 30 млн ₽ для регионов "
            "(порог после 2024 года; ранее ~6 млн ₽ среднемесячного остатка "
            "давали доступ к части сервисов)",
            _PBI_ACLUB, "Сверено: ПБИ /alfabank/5 и публичные материалы А-Клуба"),
        "concierge": _fact(
            "Есть — консьерж-сервис PRIME (входит в основные привилегии "
            "А-Клуба, бессрочно)",
            _ALFA_CONCIERGE, ""),
        "card_terms": _fact(
            "Металлическая карта: в линейке Alfa Only заказывается через "
            "персонального менеджера при среднемесячном остатке от 3 млн ₽; "
            "для клиентов A-Club доступна в составе обслуживания",
            _ALFA_ONLY, "Лимиты переводов/снятия A-Club не публикуются"),
        "addons": _ALFA_ADDONS_ABSENT,
        "service_cost": _free_on_conditions(_PBI_ACLUB),
    },
    # ----- Райффайзен -----
    "raif_premium_1": {"addons": _RAIF_ADDONS_ABSENT},
    "raif_premium_2": {"addons": _RAIF_ADDONS_ABSENT,
                       "service_cost": _free_on_conditions(
                           "https://premiumbanking.info/raiffeisen/2")},
    "raif_premium_3": {"addons": _RAIF_ADDONS_ABSENT,
                       "service_cost": _free_on_conditions(
                           "https://premiumbanking.info/raiffeisen/3")},
    # ----- Lifestyle -----
    "yandex_plus_main": {
        "delivery": _fact(
            "Бесплатная доставка из Яндекс Лавки; кэшбэк баллами 5% на "
            "Маркете (1 балл = 1 ₽ в сервисах Яндекса)",
            _YANDEX_PLUS_SUPPORT, ""),
        "taxi": _fact(
            "Кэшбэк баллами 5% в Яндекс Такси (Go), 10% в Еде, 5% в Лавке; "
            "баллы тратятся в такси и других сервисах",
            _YANDEX_PLUS_SUPPORT, ""),
    },
    "ozon_premium_main": {
        "price": _fact(
            "199 ₽/мес при помесячной оплате; 1 490 ₽/год (≈124 ₽/мес) при "
            "годовой. Периоды подписки: 30/91/182/365 дней",
            _OZON_PREMIUM_DOCS, "Сайт ozon.ru закрыт антиботом — данные из "
                                "официальных условий подписки (docs.ozon.ru)"),
        "delivery": _fact(
            "Бесплатная курьерская доставка без минимальной суммы заказа; "
            "увеличенный срок возврата до 60 дней; приоритетная поддержка; "
            "ранний доступ к распродажам и закрытые скидки",
            _OZON_PREMIUM_DOCS, ""),
        "cashback": _fact(
            "— (кэшбэк-механика не заявлена в официальных условиях подписки; "
            "денежная выгода — через закрытые скидки и ранний доступ к "
            "распродажам)",
            _OZON_PREMIUM_DOCS, "Отсутствие по официальным условиям"),
        "entertainment": _fact(
            "— (развлекательные сервисы не входят в состав Ozon Premium по "
            "официальным условиям подписки)",
            _OZON_PREMIUM_DOCS, "Отсутствие по официальным условиям"),
        "taxi": _fact(
            "— (такси/транспорт не входят в состав Ozon Premium)",
            _OZON_PREMIUM_DOCS, "Отсутствие по официальным условиям"),
        "bank_overlap": _fact(
            "доставка товаров без мин. суммы (vs возмещение Самоката и опций "
            "доставки); закрытые скидки/ранние распродажи (vs кэшбэк "
            "банковских пакетов)",
            _OZON_PREMIUM_DOCS, "Оценка пересечений по составу подписки"),
    },
    "wb_club": {
        "price": _fact(
            "199 ₽/мес (первый месяц 1 ₽); годовая — 159 ₽/мес "
            "(1 908 ₽/год)",
            _WB_CLUB_NEWS, "Сайт wildberries.ru закрыт антиботом — данные "
                           "из публичных материалов о запуске WB Клуба"),
        "cashback": _fact(
            "Механика скидок вместо кэшбэка: дополнительные скидки до 31% "
            "на товары, суммируются с персональными предложениями и акциями",
            _WB_CLUB_NEWS, ""),
        "entertainment": _fact(
            "— (развлекательные сервисы не входят в состав WB Клуба)",
            _WB_CLUB_NEWS, "Отсутствие по официальным условиям"),
        "taxi": _fact(
            "— (такси/транспорт не входят в состав WB Клуба)",
            _WB_CLUB_NEWS, "Отсутствие по официальным условиям"),
        "bank_overlap": _fact(
            "скидки на повседневные покупки (vs кэшбэк банковских пакетов); "
            "приоритетная поддержка (vs премиальная линия банка)",
            _WB_CLUB_NEWS, "Оценка пересечений по составу подписки"),
    },
}

CURATED_FACTS.update(_COMPETITOR_FACTS)

# ============================================================================
# МЕЖДУНАРОДНЫЕ БАНКИ (2026-07-02). Пороги — в оригинальной валюте
# (пересчёт — по курсам ЦБ на дату скана, лист «Методика»). «Не публикуется»
# для private-banking — особенность модели (индивидуальные условия), это
# НЕ «не найдено».
# ============================================================================

_NOT_PUBLISHED_PB = (
    "Не публикуется — обслуживание по индивидуальному предложению/приглашению "
    "(стандартная модель международного private banking: тарифной сетки в "
    "открытом доступе нет, условия обсуждаются с банком)")

_INTL_FACTS = {
    "hsbc_premier_elite": {
        "positioning": _fact(
            "Верхний retail-wealth уровень HSBC; заменил HSBC Jade с декабря "
            "2023 (существующие клиенты Jade переведены без потери привилегий)",
            "https://www.hsbc.com.hk/jade/",
            "Смена бренда Jade → Premier Elite подтверждена FAQ банка"),
        "entry_conditions": _fact(
            "От US$1 млн инвестируемых активов (в Гонконге — Total Relationship "
            "Balance от HKD 7,8 млн). Порог в оригинальной валюте",
            "https://www.hsbc.com.hk/jade/",
            "Пересчёт в ₽ — по курсу ЦБ на дату скана (метаданные скана)"),
    },
    "citi_citigold": {
        "entry_conditions": _fact(
            "Минимальный среднемесячный совокупный баланс от US$200 000 на "
            "связанных депозитных, пенсионных и инвестиционных счетах",
            "https://www.citi.com/banking/citigold", ""),
    },
    "citi_cpc": {
        "entry_conditions": _fact(
            "Минимальный среднемесячный совокупный баланс от US$1 млн",
            "https://www.citi.com/banking/citigold-private-client", ""),
    },
    "citi_private_bank": {
        "entry_conditions": _fact(_NOT_PUBLISHED_PB,
                                  "https://www.privatebank.citibank.com/",
                                  "Особенность модели, не пробел данных"),
    },
    "chase_private_client": {
        "entry_conditions": _fact(
            "Среднедневной баланс от US$150 000 в счетах и инвестициях Chase",
            "https://www.chase.com/personal/checking/private-client", ""),
    },
    "jpm_private_bank": {
        "entry_conditions": _fact(_NOT_PUBLISHED_PB,
                                  "https://privatebank.jpmorgan.com/",
                                  "Особенность модели, не пробел данных"),
    },
    "bofa_preferred_rewards": {
        "entry_conditions": _fact(
            "Многоуровневая программа по совокупному балансу: младшие уровни "
            "от ~US$20–30 тыс, высший уровень — от US$1 млн",
            "https://www.bankofamerica.com/preferred-rewards/",
            "Точные названия/пороги уровней сверять на официальной странице "
            "при следующем скане"),
    },
    "bofa_private_bank": {
        "entry_conditions": _fact(_NOT_PUBLISHED_PB,
                                  "https://www.privatebank.bankofamerica.com/",
                                  "Особенность модели, не пробел данных"),
    },
    "ubs_gwm": {
        "entry_conditions": _fact(_NOT_PUBLISHED_PB,
                                  "https://www.ubs.com/global/en/wealth-management.html",
                                  "Крупнейший private banking мира после "
                                  "объединения с Credit Suisse"),
    },
    "sc_priority": {
        "entry_conditions": _fact(
            "От S$200 000 в депозитах и/или инвестициях (или ипотека от "
            "S$1,5 млн в банке) — условия для Сингапура",
            "https://www.sc.com/sg/priority-banking/",
            "Пороги отличаются по странам присутствия"),
    },
    "db_wealth": {
        "entry_conditions": _fact(_NOT_PUBLISHED_PB,
                                  "https://www.deutschewealth.com/",
                                  "Особенность модели, не пробел данных"),
    },
    "bnp_wealth": {
        "entry_conditions": _fact(_NOT_PUBLISHED_PB,
                                  "https://wealthmanagement.bnpparibas/en.html",
                                  "Особенность модели, не пробел данных"),
    },
}

CURATED_FACTS.update(_INTL_FACTS)


def curated_for(tier_id: str) -> dict:
    return CURATED_FACTS.get(tier_id, {})
