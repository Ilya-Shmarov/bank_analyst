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
# DIGITAL-FIRST НЕОБАНКИ — Revolut, N26, Wise, Monzo (проверено 2026-07-02).
# Требование блока: НИ ОДНОГО «не найдено» — каждое поле либо заполнено с
# source_url, либо «—» с пометкой «не предусмотрено моделью продукта».
# Линейки сверены с официальными сайтами: у Monzo текущие планы —
# Extra/Perks/Max (Plus/Premium из вводной упразднены в 2024), у N26 тир
# You переименован в Go. Цены — в валюте страны (UK £ / ЕС €).
# ============================================================================

_NA = "— (не предусмотрено моделью продукта)"


def _na(url, note="Категория не применима к модели продукта"):
    return _fact(_NA, url, note)


def _ref_dashes(url):
    """Справочные поля для digital-блока: ПБИ их не покрывает."""
    return {
        "aggregator_value": _fact("— (ПБИ не покрывает международные необанки)",
                                  url, "Справочное поле"),
        "other_notes": _fact("—", url, "Справочное поле"),
        "last_change_date": _fact("— (история изменений не отслеживается "
                                  "для международного блока)", url,
                                  "Справочное поле"),
    }


# ---------- Revolut ----------
_REV_PRICING = "https://www.revolut.com/our-pricing-plans/"
_REV_PREMIUM = "https://www.revolut.com/revolut-premium/"
_REV_ULTRA = "https://www.revolut.com/ultra-plan/"
_REV_LOUNGES = "https://www.revolut.com/lounges/"

_REV_SHARED = {
    "concierge": _na(_REV_PRICING, "Консьерж-сервис не входит ни в один "
                                   "план Revolut"),
    "auto": _na(_REV_PRICING),
    "taxi_restaurants": _na(_REV_PRICING, "Компенсации такси/ресторанов "
                                          "не предусмотрены моделью"),
    "addons": _fact(
        "Разовые платные сервисы в приложении (например, lounge-пассы "
        "DragonPass); пакетных докупаемых опций нет — вместо этого апгрейд "
        "на следующий план",
        _REV_LOUNGES, ""),
    **_ref_dashes(_REV_PRICING),
}

_DIGITAL_REVOLUT = {
    "revolut_premium": {
        **_REV_SHARED,
        "positioning": _fact(
            "Первый платный уровень Revolut — travel/daily-banking подписка "
            "для активно путешествующего массового клиента",
            _REV_PREMIUM, ""),
        "entry_conditions": _fact(
            "Подписка без требований к остатку: £7,99/мес или £80/год (UK; "
            "тарифы зависят от страны)", _REV_PREMIUM, ""),
        "service_cost": _fact("£7,99/мес или £80/год (UK)", _REV_PREMIUM, ""),
        "lounge_access": _fact(
            "Проходы DragonPass покупаются со скидкой в приложении + "
            "SmartDelay: бесплатный доступ в зал при задержке рейса от 1 часа",
            _REV_LOUNGES, "Бесплатных визитов в пакете нет"),
        "cashback": _fact(
            "Баллы RevPoints за покупки по повышенному курсу относительно "
            "Standard (точный курс — в приложении; максимум по линейке — "
            "1 балл/£1 на Ultra); обмен на мили и перки",
            _REV_PRICING, ""),
        "card_terms": _fact(
            "Дебетовая карта премиального дизайна; лимит бесплатных снятий "
            "в банкоматах до £400/мес (далее комиссия); виртуальные и "
            "одноразовые карты",
            _REV_PREMIUM, ""),
        "deposits": _fact(
            "Savings-счета: ставка зависит от плана и валюты — линейка от "
            "~2,9% (Standard) до 4% годовых (Ultra); Premium — промежуточная "
            "ставка, точное значение в приложении на дату",
            _REV_PRICING, "Ставки плавающие"),
        "insurance": _fact(
            "Страхование путешествий входит начиная с Premium (медицинские "
            "расходы, задержки рейса/багажа); детали в Insurance Policy плана",
            _REV_PREMIUM, ""),
        "ecosystem": _fact(
            "Мультивалютный обмен по выгодным лимитам, международные "
            "переводы, партнёрские перки и скидки в приложении",
            _REV_PREMIUM, ""),
    },
    "revolut_metal": {
        **_REV_SHARED,
        "positioning": _fact(
            "Средний платный уровень Revolut — расширенный travel-пакет с "
            "металлической картой", _REV_PRICING, ""),
        "entry_conditions": _fact(
            "Подписка без требований к остатку: £14,99/мес (UK)",
            _REV_PRICING, ""),
        "service_cost": _fact("£14,99/мес (UK)", _REV_PRICING, ""),
        "lounge_access": _fact(
            "Проходы DragonPass со скидкой + SmartDelay (бесплатный зал при "
            "задержке рейса)", _REV_LOUNGES, ""),
        "cashback": _fact(
            "Баллы RevPoints по курсу выше, чем на Premium (точный курс в "
            "приложении); обмен на мили и перки", _REV_PRICING, ""),
        "card_terms": _fact(
            "Металлическая карта (эксклюзив уровня, одна на клиента); лимит "
            "бесплатных снятий ×4 от Standard-плана",
            "https://help.revolut.com/en-US/help/profile-and-plan/my-plan-benefits/revolut-plans1/metal-plan/",
            ""),
        "deposits": _fact(
            "Savings-счета со ставкой выше Premium (линейка до 4% на Ultra; "
            "точная ставка в приложении)", _REV_PRICING, "Ставки плавающие"),
        "insurance": _fact(
            "Расширенное страхование путешествий (медицина, задержки, багаж) "
            "— шире пакета Premium", _REV_PRICING, ""),
        "ecosystem": _fact(
            "Всё из Premium + расширенные партнёрские перки",
            _REV_PRICING, ""),
    },
    "revolut_ultra": {
        **_REV_SHARED,
        "positioning": _fact(
            "Топ-план Revolut для affluent-клиента: платиновое покрытие "
            "карты, максимальные лимиты, перки «стоимостью до £4 290/год»",
            _REV_ULTRA, ""),
        "entry_conditions": _fact(
            "Подписка без требований к остатку: £55/мес или £540/год (UK)",
            _REV_ULTRA, ""),
        "service_cost": _fact("£55/мес или £540/год (UK)", _REV_ULTRA, ""),
        "lounge_access": _fact(
            "SmartDelay (бесплатный зал при задержке рейса) + проходы "
            "DragonPass в приложении; безлимитный доступ в залы в пакете "
            "не заявлен", _REV_LOUNGES, ""),
        "cashback": _fact(
            "RevPoints: 1 балл за £1 трат — максимальный курс линейки; "
            "обмен на мили авиакомпаний и перки", _REV_ULTRA, ""),
        "card_terms": _fact(
            "Карта с платиновым покрытием (эксклюзив Ultra); снятие в "
            "банкоматах без комиссии до £2 000/мес", _REV_ULTRA, ""),
        "deposits": _fact(
            "Savings-счета до 4% годовых (максимум линейки; ставка зависит "
            "от валюты)", _REV_PRICING, "Ставки плавающие"),
        "insurance": _fact(
            "Максимальный пакет: глобальная медицина, отмена поездок и "
            "мероприятий, franchise аренды авто, зимний спорт, задержка "
            "рейса, багаж, личная ответственность", _REV_ULTRA, ""),
        "ecosystem": _fact(
            "Партнёрские подписки и travel/lifestyle-перки суммарной "
            "стоимостью до £4 290/год", _REV_ULTRA, ""),
    },
}

# ---------- N26 ----------
_N26_GO = "https://n26.com/en-eu/you-bank-account-with-travel-insurance"
_N26_METAL = "https://n26.com/en-eu/metal"
_N26_PLANS = "https://n26.com/en-eu/plans"

_N26_SHARED = {
    "concierge": _na(_N26_PLANS, "Консьерж не входит ни в один план N26"),
    "auto": _na(_N26_PLANS),
    "taxi_restaurants": _na(_N26_PLANS),
    "addons": _na(_N26_PLANS, "Докупаемых опций нет — апгрейд плана"),
    "ecosystem": _fact(
        "Партнёрские предложения и скидки в приложении; Spaces "
        "(суб-счета-конверты) для управления деньгами", _N26_PLANS, ""),
    **_ref_dashes(_N26_PLANS),
}

_DIGITAL_N26 = {
    "n26_go": {
        **_N26_SHARED,
        "positioning": _fact(
            "Средний платный план N26 (экс-You, переименован в Go) — счёт "
            "с travel-страховками для путешествующих", _N26_GO, ""),
        "entry_conditions": _fact(
            "Подписка без требований к остатку: €9,90/мес", _N26_GO, ""),
        "service_cost": _fact("€9,90/мес", _N26_GO, ""),
        "lounge_access": _fact(
            "Скидочные lounge-пассы покупаются в приложении; бесплатных "
            "визитов в пакете нет", "https://n26.com/en-eu/travel-benefits", ""),
        "cashback": _fact(
            "— (кэшбэк не предусмотрен на уровне Go; 1% за платежи за "
            "границей — только на Metal)", _N26_PLANS,
            "Отсутствие по официальной линейке планов"),
        "card_terms": _fact(
            "Цветная дебетовая Mastercard; 5 бесплатных снятий в еврозоне/мес; "
            "бесплатные снятия в иностранной валюте", _N26_GO, ""),
        "deposits": _fact(
            "Накопительный счёт N26 Instant Savings (ставка зависит от плана, "
            "максимум на Metal — 1,5% p.a.; гибкий cash fund до 2,31%)",
            _N26_PLANS, "Ставки плавающие (ЕЦБ)"),
        "insurance": _fact(
            "Travel-страховки Allianz: медицина в поездках, отмена поездки, "
            "багаж (лимиты ниже пакета Metal)", _N26_GO, ""),
    },
    "n26_metal": {
        **_N26_SHARED,
        "positioning": _fact(
            "Топ-план N26 — премиальный счёт со стальной картой и "
            "максимальными ставками/страховками; немецкая лицензия BaFin, "
            "защита депозитов €100 000", _N26_METAL, ""),
        "entry_conditions": _fact(
            "Подписка без требований к остатку: €16,90/мес", _N26_METAL, ""),
        "service_cost": _fact("€16,90/мес", _N26_METAL, ""),
        "lounge_access": _fact(
            "Скидочные lounge-пассы в приложении; бесплатных визитов нет",
            "https://n26.com/en-eu/travel-benefits", ""),
        "cashback": _fact(
            "1% кэшбэка за платежи картой вне EEA/UK/Швейцарии, без лимита "
            "суммы", _N26_METAL, ""),
        "card_terms": _fact(
            "Стальная Mastercard 18 г; 8 бесплатных снятий в еврозоне/мес "
            "(далее €2/снятие); безлимитные бесплатные снятия вне еврозоны",
            _N26_METAL, ""),
        "deposits": _fact(
            "N26 Instant Savings 1,5% p.a. + гибкий cash fund до 2,31% p.a. "
            "— максимальные ставки линейки", _N26_METAL, "Ставки плавающие"),
        "insurance": _fact(
            "Пакет Allianz: медицина до €1 млн/поездка, отмена поездки до "
            "€10 000, багаж до €2 000, смартфон до €2 000 (кража/повреждение), "
            "purchase protection", _N26_METAL, ""),
    },
}

# ---------- Wise ----------
_WISE_PRICING = "https://wise.com/us/pricing/"
_WISE_CARD = "https://wise.com/us/card/"

_DIGITAL_WISE = {
    "wise_main": {
        "positioning": _fact(
            "Мультивалютный счёт без подписки — конкурент за multi-currency "
            "lifestyle-сценарий состоятельного клиента: 40+ валют, карта, "
            "международные переводы по mid-market курсу", _WISE_CARD, ""),
        "entry_conditions": _fact(
            "Подписки и требований к остатку нет — модель pay-per-use "
            "(оплата за операции)", _WISE_PRICING, ""),
        "service_cost": _fact(
            "0/мес — без абонентской платы; выпуск карты €5 разово "
            "(замена €7)", _WISE_PRICING, ""),
        "lounge_access": _na(_WISE_PRICING, "Бизнес-залы не предусмотрены "
                                            "моделью продукта"),
        "concierge": _na(_WISE_PRICING),
        "cashback": _fact(
            "— (кэшбэк не предусмотрен моделью — ценность продукта в "
            "mid-market курсе конвертации без наценки)", _WISE_PRICING,
            "Отсутствие по модели продукта"),
        "card_terms": _fact(
            "Дебетовая карта: оплата в 40+ валютах, 160+ стран; снятия: "
            "первые 2 снятия или £200/мес бесплатно, далее ~1,75% + £1 "
            "(правила с мая 2026); конвертация 0,35–1,5% от mid-market",
            _WISE_CARD, ""),
        "deposits": _fact(
            "Wise Interest (opt-in, остатки EUR/USD/GBP): ~3,55% на EUR "
            "(май 2026, зависит от ставки ЕЦБ); Jars для хранения валют",
            _WISE_PRICING, "Ставки плавающие"),
        "insurance": _na(_WISE_PRICING, "Страхование не предусмотрено "
                                        "моделью продукта"),
        "auto": _na(_WISE_PRICING),
        "taxi_restaurants": _na(_WISE_PRICING),
        "ecosystem": _fact(
            "Международные переводы по mid-market курсу (комиссия 0,35–1,5% "
            "по паре валют, без наценки выходного дня); мультивалютные "
            "реквизиты локальных счетов (IBAN/sort code/routing)",
            _WISE_PRICING, ""),
        "addons": _na(_WISE_PRICING, "Опций нет — pay-per-use за операции"),
        **_ref_dashes(_WISE_PRICING),
    },
}

# ---------- Monzo ----------
_MONZO_PLANS = "https://monzo.com/current-account/plans"
_MONZO_PERKS = "https://monzo.com/current-account/perks"
_MONZO_MAX = "https://monzo.com/help/monzo-max/monzo-max-what"
_MONZO_LOUNGE = "https://monzo.com/help/monzo-premium/how-to-airport-lounge"

_MONZO_SHARED = {
    "concierge": _na(_MONZO_PLANS, "Консьерж не входит ни в один план Monzo"),
    "taxi_restaurants": _na(_MONZO_PLANS),
    "addons": _fact(
        "Max можно расширить пакетом Family (+£5/мес: страховки на членов "
        "семьи); других докупаемых опций нет", _MONZO_MAX, ""),
    "card_terms": _fact(
        "Стандартная дебетовая карта Monzo (премиальных носителей в линейке "
        "Extra/Perks/Max нет); лимиты бесплатных снятий за границей выше на "
        "платных планах (детали в Help Centre)", _MONZO_PLANS, ""),
    **_ref_dashes(_MONZO_PLANS),
}

_DIGITAL_MONZO = {
    "monzo_extra": {
        **_MONZO_SHARED,
        "positioning": _fact(
            "Начальный платный план Monzo (линейка Extra/Perks/Max заменила "
            "Plus/Premium в 2024)", _MONZO_PLANS, ""),
        "entry_conditions": _fact(
            "Подписка без требований к остатку: £3/мес", _MONZO_PLANS, ""),
        "service_cost": _fact("£3/мес (£36/год)", _MONZO_PLANS, ""),
        "lounge_access": _na(_MONZO_PLANS, "Lounge-доступ — только на Max"),
        "cashback": _fact(
            "Billsback: возврат по оплате счетов — шанс получить счёт "
            "оплаченным до £150/счёт в месяц (механика розыгрыша, не "
            "фиксированный процент)", _MONZO_PLANS, ""),
        "deposits": _fact(
            "Сберегательные счета: стандартные ставки 2,75% AER (Instant "
            "Access) / 3,15% AER (Select Access) — буст ставок начинается "
            "с Perks", _MONZO_PLANS, "Ставки плавающие"),
        "insurance": _na(_MONZO_PLANS, "Страховки — только на Max"),
        "auto": _na(_MONZO_PLANS, "Breakdown cover — только на Max"),
        "ecosystem": _fact(
            "Connected banks (агрегация чужих счетов), credit insights, "
            "Billsback", _MONZO_PLANS, ""),
    },
    "monzo_perks": {
        **_MONZO_SHARED,
        "positioning": _fact(
            "Средний план Monzo — lifestyle-перки повседневного использования",
            _MONZO_PERKS, ""),
        "entry_conditions": _fact(
            "Подписка без требований к остатку: £7/мес", _MONZO_PERKS, ""),
        "service_cost": _fact("£7/мес (£84/год)", _MONZO_PERKS, ""),
        "lounge_access": _na(_MONZO_PLANS, "Lounge-доступ — только на Max"),
        "cashback": _fact(
            "Billsback до £150/счёт в месяц + натуральные перки: еженедельный "
            "Greggs, годовой Railcard, ежемесячный билет Vue, подписка "
            "Uber One", _MONZO_PERKS, ""),
        "deposits": _fact(
            "Буст ставок +0,50% AER: 3,25% AER Instant Access / до 3,65% "
            "AER Select Access", _MONZO_PERKS, "Ставки плавающие"),
        "insurance": _na(_MONZO_PLANS, "Страховки — только на Max"),
        "auto": _na(_MONZO_PLANS, "Breakdown cover — только на Max"),
        "ecosystem": _fact(
            "Всё из Extra + Greggs/Railcard/Vue/Uber One — прямая аналогия "
            "механики «опций» рублёвых банков", _MONZO_PERKS, ""),
    },
    "monzo_max": {
        **_MONZO_SHARED,
        "positioning": _fact(
            "Топ-план Monzo — страховой пакет + travel-перки (аналог "
            "packaged account)", _MONZO_MAX, ""),
        "entry_conditions": _fact(
            "Подписка без требований к остатку: £17/мес (Max) или £22/мес "
            "(Max with Family)", _MONZO_MAX, ""),
        "service_cost": _fact("£17/мес (£204/год); Family — £22/мес",
                              _MONZO_MAX, ""),
        "lounge_access": _fact(
            "Скидочный доступ LoungeKey: 1 100+ залов по фиксированной цене "
            "£24/чел/визит (бесплатных визитов нет)", _MONZO_LOUNGE, ""),
        "cashback": _fact(
            "Billsback до £150/счёт в месяц + перки Perks (Greggs, Railcard, "
            "Vue, Uber One)", _MONZO_MAX, ""),
        "deposits": _fact(
            "Бустнутые ставки: 3,25% AER Instant Access / до 3,65% AER "
            "Select Access", _MONZO_MAX, "Ставки плавающие"),
        "insurance": _fact(
            "Worldwide travel insurance + страховка телефона; членов семьи "
            "можно добавить за +£5/мес", _MONZO_MAX, ""),
        "auto": _fact(
            "Breakdown cover UK & Europe (помощь на дорогах — эвакуация/"
            "техпомощь) — входит в Max", _MONZO_MAX, ""),
        "ecosystem": _fact(
            "Всё из Extra и Perks + страховой пакет; connected banks, "
            "credit insights", _MONZO_MAX, ""),
    },
}

CURATED_FACTS.update(_DIGITAL_REVOLUT)
CURATED_FACTS.update(_DIGITAL_N26)
CURATED_FACTS.update(_DIGITAL_WISE)
CURATED_FACTS.update(_DIGITAL_MONZO)


def curated_for(tier_id: str) -> dict:
    return CURATED_FACTS.get(tier_id, {})
