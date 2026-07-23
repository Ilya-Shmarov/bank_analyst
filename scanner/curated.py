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
_SBER_PREMIUM_LEVELS = "https://www.sberbank.ru/ru/person/premium"
_SBER_FIRST = "https://www.sberbank.ru/first"
_SBER_VKLAD = "https://www.sberbank.ru/ru/person/premium/premium_vklad"
_SBER_FIRST_VKLADY = "https://www.sberbank.ru/ru/person/sb1/vklad/vse_vklady"
_SBER_CARD = "https://www.sberbank.ru/ru/person/bank_cards/debit/sberkarta_premium"
_PBI_SBER = "https://premiumbanking.info/sber"
_ALFA_ACLUB_OFFICIAL = "https://alfabank.ru/a-club/"

_CHECKED = "2026-07-02"


def _fact_from(source_fact, value, note=""):
    return {
        "value": value,
        "source_url": source_fact["source_url"],
        "date_checked": source_fact["date_checked"],
        "note": note or source_fact.get("note", ""),
    }

# ---------- Карты (Премиальная СберКарта, тарифы одной страницы для всех уровней)
_PREMIER_CARD = {
    "value": ("Премиальная СберКарта: пластик или металл (металлический носитель "
              "доступен всем премиальным уровням). Снятие наличных до 1 млн ₽ "
              "в день. Стоимость "
              "выпуска металлической карты на странице тарифов не указана"),
    "source_url": _SBER_CARD,
    "date_checked": _CHECKED,
    "note": "Лимиты переводов зависят от уровня и хранятся отдельными фактами",
}

_FIRST_CARD = {
    "value": ("Премиальная СберКарта: пластик или металл. Снятие наличных "
              "до 2 млн ₽ в день"),
    "source_url": _SBER_CARD,
    "date_checked": _CHECKED,
    "note": ("Вторичные источники (banki.ru) упоминали выпуск металлической "
             "карты СберПервый за 7 500 ₽ — на официальной странице цена "
             "не опубликована, требует сверки в тарифах PDF"),
}

_PRIVATE_CARD = {
    "value": ("Премиальная СберКарта уровня Private: снятие наличных до "
              "3 млн ₽ в день; "
              "лимитированная серия металлических карт (чёрные и белые) — "
              "только для уровня 6 / Sber Private Banking"),
    "source_url": _SBER_CARD,
    "date_checked": _CHECKED,
    "note": "Лимит переводов уровня 6 хранится отдельным фактом",
}

# Официальный popup «Переводы и платежи без комиссии» задаёт разные лимиты
# для конкретных уровней. Не объединять и не переносить их между тирами.
_SBER_TRANSFER_LEVELS = {
    "sber_premier_1": {
        "value": "Переводы без комиссии до 1 млн ₽ в месяц",
        "source_url": _SBER_PREMIUM_LEVELS,
        "date_checked": "2026-07-23",
        "note": ("Официальный popup: «1 и 2 уровни — 1 млн ₽ в месяц». "
                 "Лимит относится к переводам клиентам Сбера и платежам юрлицам"),
    },
    "sber_premier_2": {
        "value": "Переводы без комиссии до 1 млн ₽ в месяц",
        "source_url": _SBER_PREMIUM_LEVELS,
        "date_checked": "2026-07-23",
        "note": ("Официальный popup: «1 и 2 уровни — 1 млн ₽ в месяц». "
                 "Лимит относится к переводам клиентам Сбера и платежам юрлицам"),
    },
    "sber_premier_3": {
        "value": "Переводы без комиссии до 1 млн ₽ в сутки",
        "source_url": _SBER_PREMIUM_LEVELS,
        "date_checked": "2026-07-23",
        "note": ("Официальный popup: «3 уровень — 1 млн ₽ в сутки». "
                 "Лимит относится к переводам клиентам Сбера и платежам юрлицам"),
    },
    "sber_first_4": {
        "value": "Переводы без комиссии до 35 млн ₽ в сутки",
        "source_url": _SBER_PREMIUM_LEVELS,
        "date_checked": "2026-07-23",
        "note": ("Официальный popup: «4 и 5 уровни — 35 млн ₽ в сутки». "
                 "Лимит относится к переводам клиентам Сбера и платежам юрлицам"),
    },
    "sber_first_5": {
        "value": "Переводы без комиссии до 35 млн ₽ в сутки",
        "source_url": _SBER_PREMIUM_LEVELS,
        "date_checked": "2026-07-23",
        "note": ("Официальный popup: «4 и 5 уровни — 35 млн ₽ в сутки». "
                 "Лимит относится к переводам клиентам Сбера и платежам юрлицам"),
    },
    "sber_private_6": {
        "value": "Переводы без комиссии до 50 млн ₽ в сутки",
        "source_url": _SBER_PREMIUM_LEVELS,
        "date_checked": "2026-07-23",
        "note": ("Официальный popup: «6 уровень — до 50 млн ₽ в сутки». "
                 "Лимит относится к переводам клиентам Сбера и платежам юрлицам"),
    },
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

_SBER_FIRST_4_ECOSYSTEM = {
    "value": (
        "СберПрайм, Okko «Премиум» с Amediateka; "
        "Обмен 10 бонусов = 8 ₽ с лимитом 12 500 Б в мес; "
        "Консьерж Aspire; "
        "Компенсация БЗ за границей по 3 тыс ₽ на 1 чел; "
        "Бизнес-зал Сбер в SVO"
    ),
    "source_url": f"{_PBI_SBER}/4",
    "date_checked": "2026-07-14",
    "note": "Закреплено из блока «Другие привилегии» для уровня 4; официальный сайт отдавал битую кодировку.",
}

_SBER_FIRST_5_ECOSYSTEM = {
    "value": (
        "СберПрайм, Okko «Премиум» с Amediateka; "
        "Обмен 10 бонусов = 8 ₽ с лимитом 12 500 Б в мес; "
        "Консьерж Aspire; "
        "Компенсация БЗ за границей по 3 тыс ₽ на 1 чел; "
        "Бизнес-зал Сбер в SVO"
    ),
    "source_url": f"{_PBI_SBER}/5",
    "date_checked": "2026-07-14",
    "note": "Закреплено из блока «Другие привилегии» для уровня 5; официальный сайт отдавал битую кодировку.",
}

_SBER_PRIVATE_ECOSYSTEM = {
    "value": (
        "СберПрайм, Okko «Премиум» с Amediateka; "
        "Компенсация ВИП-залов до 5 тыс ₽ в одном городе; "
        "Компенсация БЗ до 5 тыс ₽, если нет в списке; "
        "Бизнес-зал Сбер в SVO без ограничений; "
        "3 консультации в год СберПраво; "
        "Консьерж Pb Service; "
        "Сбер Мобайл: звонки + 5 ГБ в месяц; "
        "Обмен 10 бонусов = 8 ₽ с лимитом 12 500 Б в мес"
    ),
    "source_url": f"{_PBI_SBER}/6",
    "date_checked": "2026-07-14",
    "note": "Закреплено из блока «Другие привилегии» для уровня 6.",
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
        "transfers_payments": _SBER_TRANSFER_LEVELS["sber_premier_1"],
        "cash_withdrawal": _fact_from(
            _PREMIER_CARD, "Снятие наличных до 1 млн ₽ в день"),
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
        "transfers_payments": _SBER_TRANSFER_LEVELS["sber_premier_2"],
        "cash_withdrawal": _fact_from(
            _PREMIER_CARD, "Снятие наличных до 1 млн ₽ в день"),
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
        "transfers_payments": _SBER_TRANSFER_LEVELS["sber_premier_3"],
        "cash_withdrawal": _fact_from(
            _PREMIER_CARD, "Снятие наличных до 1 млн ₽ в день"),
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
        "transfers_payments": _SBER_TRANSFER_LEVELS["sber_first_4"],
        "cash_withdrawal": _fact_from(
            _FIRST_CARD, "Снятие наличных до 2 млн ₽ в день"),
        "deposits": _FIRST_DEPOSITS,
        "ecosystem": _SBER_FIRST_4_ECOSYSTEM,
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
        "transfers_payments": _SBER_TRANSFER_LEVELS["sber_first_5"],
        "cash_withdrawal": _fact_from(
            _FIRST_CARD, "Снятие наличных до 2 млн ₽ в день"),
        "deposits": _FIRST_DEPOSITS,
        "ecosystem": _SBER_FIRST_5_ECOSYSTEM,
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
        "transfers_payments": _SBER_TRANSFER_LEVELS["sber_private_6"],
        "cash_withdrawal": _fact_from(
            _PRIVATE_CARD, "Снятие наличных до 3 млн ₽ в день"),
        "deposits": _FIRST_DEPOSITS,
        "ecosystem": _SBER_PRIVATE_ECOSYSTEM,
    },
}


# ============================================================================
# КОНКУРЕНТЫ — целевое дозаполнение пустых полей (2026-07-02).
# Значение «— (…)» = услуга отсутствует по официальным условиям тира
# (НЕ путать с «не найдено» — то уходит в лист «Требует ручной проверки»).
# ============================================================================

def _fact(value, url, note="", date_checked=None):
    return {"value": value, "source_url": url,
            "date_checked": date_checked or _CHECKED, "note": note}


def _free_on_conditions(pbi_url):
    return _fact("0 ₽ — бесплатно при выполнении условий уровня (остаток/траты/"
                 "акции определяют сам уровень, отдельная плата не предусмотрена)",
                 pbi_url, "Выведено из условий входа уровня (ПБИ)")


# ---------- Т-Банк ----------
_TBANK_PREMIUM = "https://www.tbank.ru/tinkoff-premium/"
_TBANK_SAVINGS = "https://www.tbank.ru/savings/saving-account/"
_TBANK_PRIVATE_BANKING = "https://www.tbank.ru/private/banking-services/"
_TBANK_PREMIUM_ACCESS = (
    "https://www.tbank.ru/bank/help/general/premium/access/what-is/"
)
_TBANK_PREMIUM_TERMS = (
    "https://www.tbank.ru/bank/help/general/premium/access/terms/"
)
_TBANK_SERVICES = "https://www.tbank.ru/bank/help/general/premium/services/"
_TBANK_CARD = ("https://www.tbank.ru/tinkoff-premium/cards/debit-cards/"
               "tinkoff-black-premium/")
_TBANK_PREMIUM_TARIFF = (
    "https://cdn.tbank.ru/static/documents/docs-terms-of-service-premium.pdf")
_TBANK_PRIVATE_TARIFF = (
    "https://cdn.tbank.ru/static/documents/docs-terms-of-service-private.pdf")

_TBANK_PREMIUM_TRANSFERS = _fact(
    "Лимит бесплатных переводов с расчётной карты Т-Банка на карту другого "
    "банка через сервисы Т-Банка — 100 000 ₽ в расчётном периоде по всем "
    "счетам. Лимит бесплатных переводов с кредитной карты: Bronze — "
    "150 000 ₽, Silver/Gold/Diamond — 200 000 ₽ в расчётном периоде",
    _TBANK_PREMIUM_TARIFF,
    "Официальные условия сервиса Premium, раздел «Тарифы Сервиса»")

_TBANK_PREMIUM_CASH_WITHDRAWAL = _fact(
    "Снятие наличных по расчётным картам: в банкоматах Т-Банка — бесплатно; "
    "в других банкоматах — бесплатно в расчётном периоде в 2 раза больше "
    "относительно суммы, указанной в тарифе карты",
    _TBANK_PREMIUM_TARIFF,
    "Официальные условия сервиса Premium, раздел «Тарифы Сервиса»")

_TBANK_PREMIUM_SUPREME = _fact(
    "Карта может быть переключена с «МИР (Продвинутая)» на Mir Supreme при "
    "активном сервисе Premium 32 дня подряд и покупках от 137 000 ₽ за "
    "последние три календарных месяца",
    _TBANK_PREMIUM_TARIFF,
    "Официальные условия сервиса Premium, пункт 6.8")

_TBANK_BRONZE_ENTRY = _fact(
    "Premium Bronze доступен любому клиенту за 2 990 ₽ в месяц",
    _TBANK_PREMIUM_TERMS,
    "Официальная справка Т-Банка: у Bronze нет условия входа через акции; "
    "вариант «5 000 акций» из PBI не применяется",
    date_checked="2026-07-23")

_TBANK_BRONZE_POSITIONING = _fact(
    "Premium Bronze — платный базовый уровень сервиса Premium, доступный "
    "любому клиенту Т-Банка",
    _TBANK_PREMIUM_TERMS,
    "Официальная справка Т-Банка; условие через акции отсутствует",
    date_checked="2026-07-23")

_TBANK_BRONZE_SERVICE_COST = _fact(
    "2 990 ₽ в месяц",
    _TBANK_PREMIUM_TERMS,
    "Официальная справка Т-Банка, стоимость Premium Bronze",
    date_checked="2026-07-23")

_TBANK_SILVER_ENTRY = _fact(
    "3 млн ₽ на счетах; или 1 млн ₽ на счетах и траты 200 тыс ₽ в месяц; "
    "или зарплата 400 тыс ₽ в текущем месяце или в среднем за три "
    "предыдущих календарных месяца",
    _TBANK_PREMIUM_ACCESS,
    "Официальная справка Т-Банка, условия бесплатного уровня Premium Silver",
    date_checked="2026-07-21")

_TBANK_PRIVATE_TRANSFERS = _fact(
    "Лимит бесплатных переводов с расчётной карты Т-Банка на карту другого "
    "банка через сервисы Т-Банка — 500 000 ₽ в расчётном периоде по всем "
    "счетам. Лимит бесплатных переводов с кредитной карты Т-Банка — "
    "500 000 ₽ в расчётном периоде по всем кредитным картам, кроме тарифных "
    "планов кредитных карт из линейки 11.X",
    _TBANK_PRIVATE_TARIFF,
    "Официальные условия сервиса Private, раздел «Тарифы Сервиса»")

_TBANK_PRIVATE_CASH_WITHDRAWAL = _fact(
    "Снятие наличных по расчётным картам: в банкоматах Т-Банка — бесплатно; "
    "в других банкоматах — бесплатно в расчётном периоде в 10 раз больше "
    "относительно суммы, указанной в тарифе карты в рублях РФ, или в 2 раза "
    "больше относительно суммы, указанной в тарифе карты в иностранной валюте, "
    "без ограничения по минимальной сумме операции",
    _TBANK_PRIVATE_TARIFF,
    "Официальные условия сервиса Private, раздел «Тарифы Сервиса»")

_TBANK_PRIVATE_SUPREME = _fact(
    "Карта может быть переключена с «МИР (Продвинутая)» на Mir Supreme при "
    "активном сервисе Private 32 дня подряд и покупках от 137 000 ₽ за "
    "последние три календарных месяца; обратное переключение — при отключении "
    "сервиса Private",
    _TBANK_PRIVATE_TARIFF,
    "Официальные условия сервиса Private, пункт 4.6")


def _tbank_private_restaurants(pbi_url):
    return _fact(
        "Безлимитные компенсации: до 5 000 ₽ на один посадочный талон в "
        "России и до 50 $ за границей. Только в ресторане аэропорта вылета, "
        "не более чем за сутки до вылета; компенсация по кнопке в приложении "
        "или через чат, чек разбивать не требуется",
        pbi_url,
        "Лимит 5 000 ₽ применяется к одному посадочному талону, а не к месяцу; "
        "месячного и годового денежного лимита источник не указывает",
        date_checked="2026-07-21")

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

_TBANK_PREMIUM_SHARED = {
    **_TBANK_SHARED,
    "deposits": _fact(
        "Накопительный счёт — 9% годовых с сервисом Premium",
        _TBANK_SAVINGS,
        "Официальная страница накопительного счёта: 9% с Premium, "
        "6% без подписки и премиального сервиса",
        date_checked="2026-07-23"),
    "transfers_payments": _TBANK_PREMIUM_TRANSFERS,
    "cash_withdrawal": _TBANK_PREMIUM_CASH_WITHDRAWAL,
    "supreme": _TBANK_PREMIUM_SUPREME,
}

_TBANK_PRIVATE_SHARED = {
    **_TBANK_SHARED,
    "deposits": _fact(
        "Накопительный счёт — 10% годовых с сервисом Private",
        _TBANK_PRIVATE_BANKING,
        "Официальная страница банковских услуг T-Private",
        date_checked="2026-07-23"),
    "transfers_payments": _TBANK_PRIVATE_TRANSFERS,
    "cash_withdrawal": _TBANK_PRIVATE_CASH_WITHDRAWAL,
    "supreme": _TBANK_PRIVATE_SUPREME,
}

# ---------- ВТБ (Привилегия, уровни 1–4) ----------
_VTB_SERVICES = "https://www.vtb.ru/privilegia/premialnye-servisy/"
_VTB_CARD = ("https://www.vtb.ru/privilegia/karty/debetovye/"
             "privilegiya-mir-supreme/")
_VTB_MAIN = "https://www.vtb.ru/privilegia/"
_VTB_CHECKED = "2026-07-15"

_VTB_PRIVILEGE_1_ENTRY = _fact(
    "3 990 ₽ в месяц; или траты 150 тыс ₽ в месяц; или зарплата 300 тыс ₽ "
    "в месяц; или зарплата 700 тыс ₽ суммарно за три полных последовательных "
    "календарных месяца; или 9 000 акций банка ВТБ",
    _VTB_MAIN,
    "Официальная страница ВТБ; добавлен отдельный трёхмесячный зарплатный "
    "критерий, не выделенный в PBI",
    date_checked="2026-07-21")

_VTB_CASHBACK = _fact(
    "Кэшбэк рублями по карте ВТБ «Привилегия Mir Supreme»: до 30 000 ₽ "
    "в месяц за покупки в выбранных категориях; 3 категории из 9 "
    "ежемесячно, плюс 1 категория для зарплатных клиентов; отдельные "
    "категории могут иметь собственные лимиты",
    _VTB_CARD,
    "Официальная страница карты ВТБ «Привилегия Mir Supreme»: кэшбэк "
    "рублями до 30 000 ₽, 3 категории из 9 + 1 для зарплатных клиентов",
    _VTB_CHECKED)

_VTB_DEPOSITS = _fact(
    "Накопительный ВТБ-Счёт до 13,6% годовых; повышенная ставка за "
    "покупки по дебетовой карте, проценты начисляются на минимальный / "
    "ежедневный остаток",
    _VTB_MAIN,
    "Официальная страница ВТБ «Привилегия»: доходность по новому "
    "накопительному ВТБ-Счёту до 13,6%",
    _VTB_CHECKED)

_VTB_PRIVILEGE_SHARED = {
    "concierge": _fact(
        "Есть — круглосуточный консьерж-сервис, бесплатно для всех клиентов "
        "«Привилегии»: юридическая, деловая и медицинская поддержка, "
        "путешествия/досуг, детский консьерж",
        _VTB_SERVICES, ""),
    "cashback": _VTB_CASHBACK,
    "deposits": _VTB_DEPOSITS,
    "card_terms": _fact(
        "Карта «Привилегия Mir Supreme» (есть цифровая версия). Снятие без "
        "комиссии в банкоматах ВТБ и партнёров группы: до 350 000 ₽/день, "
        "до 2 млн ₽/мес",
        _VTB_CARD, ""),
    "cash_withdrawal": _fact(
        "Снятие без комиссии в банкоматах ВТБ и партнёров группы: "
        "до 350 000 ₽ в день, до 2 млн ₽ в месяц",
        _VTB_CARD, ""),
    "supreme": _fact(
        "Карта «Привилегия Mir Supreme»; есть цифровая версия",
        _VTB_CARD, ""),
    "auto": _fact(
        "Есть — «Помощь на дорогах»: эвакуатор, техническая и юридическая "
        "поддержка (для поездок на личном автомобиле)",
        _VTB_SERVICES, ""),
}

# ---------- Озон Банк (Ultra) ----------
_OZON_PRODUCTS = "https://finance.ozon.ru/products"
_OZON_HELP = "https://help-bank.ozon.ru/individuals/bonuses-and-promotions"
_OZON_SAVINGS = "https://finance.ozon.ru/promo/savings/landing"
_OZON_DEPOSIT = "https://finance.ozon.ru/promo/deposit/landing"
_OZON_ULTRA_TARIFF = (
    "https://cdn1.ozone.ru/s3/ob-landing/static/docs/ecom/products/rules/"
    "2026.05.18%20-%20Тариф%20Ultra.pdf")

_OZON_DEPOSITS_FACT = _fact(
    "Накопительный счёт: до 15,1% годовых для новых клиентов до 2 месяцев, "
    "далее 12,5% при выполнении условий или 8% базовая ставка; вклад: "
    "до 13,5% годовых с ежемесячной капитализацией",
    _OZON_DEPOSIT,
    "Официальные страницы Ozon Банка: вклад до 13,5%; накопительный счёт "
    f"до 15,1% / 12,5% / 8% ({_OZON_SAVINGS})")

_OZON_ULTRA_TRANSFERS = _fact(
    "Пополнение через сервис пополнения по карте — бесплатно. Перевод "
    "денежных средств с использованием реквизитов карты через сторонние "
    "сервисы переводов при MCC 6538 — бесплатно; отдельный лимит по этой "
    "строке тарифа Ultra не указан",
    _OZON_ULTRA_TARIFF,
    "Официальный тариф Ultra, раздел операций по карте")

_OZON_ULTRA_SUPREME = _fact(
    "Карта категории Mir Supreme: пластиковая карта — выпуск/перевыпуск "
    "не более 1 карты бесплатно, обслуживание на период действия тарифа "
    "Ultra бесплатно; металлическая карта Mir Supreme — выпуск/перевыпуск "
    "не более 1 карты бесплатно, обслуживание на период действия тарифа "
    "Ultra бесплатно",
    _OZON_ULTRA_TARIFF,
    "Официальный тариф Ultra, блок «Карта категории Mir Supreme»")


def _ozon_ultra_cash_withdrawal(renewal_limit: str) -> dict:
    return _fact(
        "Выдача наличных по карте (снятие в банкоматах и т.д.) — бесплатно "
        "во всех банкоматах на территории РФ в рамках лимитов. При первичном "
        "подключении тарифа Ultra: 3 000 000 ₽ дневной / 3 000 000 ₽ месячный "
        f"лимит. При продлении тарифа Ultra: {renewal_limit} дневной / "
        f"{renewal_limit} месячный лимит",
        _OZON_ULTRA_TARIFF,
        "Официальный тариф Ultra, блок выдачи наличных")


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
    "transfers_payments": _OZON_ULTRA_TRANSFERS,
    "supreme": _OZON_ULTRA_SUPREME,
    "deposits": _OZON_DEPOSITS_FACT,
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
_GPB_PREMIUM = "https://www.gazprombank.ru/premium/"
_GPB_PRIVATE = "https://www.gazprombank.ru/private/"

_GPB_PREMIUM_1_ENTRY = _fact(
    "2,5 млн ₽ среднемесячных остатков; или траты 150 тыс ₽ в месяц; или "
    "1 млн ₽ среднемесячных остатков и траты 100 тыс ₽ в месяц; или "
    "зарплата 250 тыс ₽ и траты 50 тыс ₽ в месяц; или 2 990 ₽ в месяц",
    _GPB_BONUS,
    "Официальная страница условий бесплатности Газпром Бонус «Премиум»",
    date_checked="2026-07-21")

_GPB_PREMIUM_2_ENTRY = _fact(
    "6 млн ₽ среднемесячных остатков; или зарплата 750 тыс ₽ и траты "
    "100 тыс ₽ в месяц",
    "https://premiumbanking.info/gazprombank/2",
    "Точное условие уровня 2 подтверждено в профильном источнике; на "
    "официальной странице отдельная граница уровня не выделена",
    date_checked="2026-07-21")

_GPB_PREMIUM_DEPOSITS = _fact(
    "Надбавки по вкладам и накопительным счетам; доход по вкладам до 13,6%",
    _GPB_PREMIUM,
    "Официальная страница премиальной карты Газпромбанка")

_GPB_PREMIUM_TRANSFERS = _fact(
    "Переводы по номеру телефона бесплатно до 200 000 ₽; переводы по номеру "
    "карты бесплатно до 50 000 ₽",
    _GPB_PREMIUM,
    "Официальный блок «Короткие тарифы» премиальной карты Газпромбанка")

_GPB_PREMIUM_CASH = _fact(
    "Снятие наличных бесплатно при выполнении условий тарифа",
    _GPB_PREMIUM,
    "Официальный блок «Короткие тарифы» премиальной карты Газпромбанка")

_GPB_PREMIUM_SUPREME = _fact(
    "Премиальная карта Газпромбанка на платёжной системе МИР Supreme; "
    "можно оформить до 4 дополнительных карт Mir Supreme бесплатно",
    _GPB_PREMIUM,
    "Официальная страница премиальной карты Газпромбанка")

_GPB_PRIVATE_DEPOSITS = _fact(
    "Вклады и накопительные счета: выгодные условия для клиентов Private Banking",
    _GPB_PRIVATE,
    "Официальная страница Gazprombank Private Banking")

# ---------- Альфа-Банк ----------
_ALFA_ONLY = "https://alfabank.ru/everyday/alfa-only/"
_ALFA_ONLY_DEPOSIT = "https://alfabank.ru/everyday/package/premium/vklad/"
_ALFA_ONLY_SALARY = (
    "https://alfabank.ru/everyday/debit-cards/premium/zarplatnaya-karta/"
)
_ALFA_ACLUB_OFFICIAL = "https://alfabank.ru/a-club/"
_ALFA_CONCIERGE = "https://alfabank.ru/everyday/package/premium/konserzh-servis/"
_PBI_ACLUB = "https://premiumbanking.info/alfabank/5"
_ALFA_ONLY_CARD_TARIFFS = (
    "https://alfabank.servicecdn.ru/site-upload/c1/65/275/"
    "Tariffs_Alfa_Only_Card.pdf"
)

_ALFA_CONCIERGE_FACT = _fact(
    "Есть — консьерж-сервис для клиентов Alfa Only (официальная страница "
    "«Консьерж-сервис — премиум-услуги для клиентов Alfa Only»)",
    _ALFA_CONCIERGE,
    "Ложное «нет» из автопарсинга ПБИ исправлено по официальному сайту")

_ALFA_ONLY_1_ENTRY = _fact(
    "2 990 ₽ в месяц; или зарплата 400 тыс ₽ в месяц через зарплатный "
    "сервис Альфа-Банка",
    _ALFA_ONLY_SALARY,
    "Официальная зарплатная страница подтверждает порог; привязка к "
    "базовому уровню Alfa Only подтверждена PBI",
    date_checked="2026-07-21")

_ALFA_ADDONS_ABSENT = _fact(
    "— (докупаемых опций нет: набор привилегий Alfa Only фиксированный — "
    "Lounge, металлическая карта, партнёрские программы, премиальный вклад, "
    "привилегии в ресторанах)",
    _ALFA_ONLY, "Отсутствие по официальному составу пакета")

_ALFA_ONLY_CASHBACK = _fact(
    "Кэшбэк по карте Alfa Only: 7% в 5 категориях либо 7% в 4 категориях "
    "+ 1% на всё; максимальный месячный лимит кэшбэка 30 000 ₽; "
    "суперкэшбэк до 100% как отдельная промо-механика; категории выбираются "
    "ежемесячно",
    _ALFA_ONLY_CARD_TARIFFS,
    "Официальный PDF Tariffs_Alfa_Only_Card.pdf; суперкэшбэк не трактуется "
    "как стандартный кэшбэк на все покупки")

_ALFA_ONLY_CARD_FREE = _fact(
    "Карта Alfa Only обслуживается бесплатно",
    _ALFA_ONLY_CARD_TARIFFS,
    "Официальный тарифный PDF по карте Alfa Only")

_ALFA_ONLY_TRANSFERS = _fact(
    "Через приложение Альфа-Банка или Альфа-Онлайн бесплатно: пополнение "
    "с карты другого банка, перевод клиенту банка, оплата коммунальных услуг, "
    "мобильной связи и штрафов ГИБДД, переводы по реквизитам счёта в рублях "
    "и валюте, перевод по номеру телефона. Перевод на карту другого банка "
    "по номеру карты — бесплатно до 100 000 ₽ в месяц; при превышении лимита "
    "и остатках до 12 млн ₽ — комиссия 1,95%, минимум 49 ₽; при остатках "
    "от 12 млн ₽ — без комиссии и ограничений",
    _ALFA_ONLY_CARD_TARIFFS,
    "Официальный тарифный PDF по карте Alfa Only, раздел 6")

_ALFA_ONLY_CASH_WITHDRAWAL = _fact(
    "Снятие наличных в банкоматах других банков по миру — бесплатно",
    _ALFA_ONLY_CARD_TARIFFS,
    "Официальный тарифный PDF по карте Alfa Only, пункт 3")

_ALFA_ONLY_SUPREME = _fact(
    "Supreme в тарифе карты Alfa Only не заявлен; в Alfa Only бесплатно "
    "выпускаются и обслуживаются карты Alfa Only, Alfa Only Aeroflot и "
    "Alfa Only Travel",
    _ALFA_ONLY_CARD_TARIFFS,
    "Официальный тарифный PDF по карте Alfa Only, блок премиальных карт")

_ALFA_ONLY_DEPOSITS = _fact(
    "Премиум-вклад Alfa Only: до 13,8% годовых в рублях или до 4% годовых "
    "в юанях; минимальная сумма 10 000 ₽ или 500 ¥; срок от 2 месяцев до "
    "3 лет; с капитализацией процентов или без неё",
    _ALFA_ONLY_DEPOSIT,
    "Официальная продуктовая страница подтверждает условия для клиентов "
    "Alfa Only без разделения по уровням",
    date_checked="2026-07-21")

_ALFA_ACLUB_DEPOSITS = _fact(
    "Повышенный доход по накопительным счетам и вкладам",
    _ALFA_ACLUB_OFFICIAL,
    "Официальная страница A-Club")

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
    "tbank_bronze": {
        **_TBANK_PREMIUM_SHARED,
        "positioning": _TBANK_BRONZE_POSITIONING,
        "entry_conditions": _TBANK_BRONZE_ENTRY,
        "service_cost": _TBANK_BRONZE_SERVICE_COST,
    },
    "tbank_silver": {**_TBANK_PREMIUM_SHARED,
                     "entry_conditions": _TBANK_SILVER_ENTRY,
                     "service_cost": _free_on_conditions(
                         "https://premiumbanking.info/tbank/2")},
    "tbank_gold": {**_TBANK_PREMIUM_SHARED,
                   "service_cost": _free_on_conditions(
                       "https://premiumbanking.info/tbank/3")},
    "tbank_diamond": {**_TBANK_PREMIUM_SHARED,
                      "service_cost": _free_on_conditions(
                          "https://premiumbanking.info/tbank/4")},
    "tbank_private_30": {**_TBANK_PRIVATE_SHARED,
                         "restaurants": _tbank_private_restaurants(
                             "https://premiumbanking.info/tbank/5"),
                         "service_cost": _free_on_conditions(
                             "https://premiumbanking.info/tbank/5")},
    "tbank_private_55": {**_TBANK_PRIVATE_SHARED,
                         "restaurants": _tbank_private_restaurants(
                             "https://premiumbanking.info/tbank/6"),
                         "service_cost": _free_on_conditions(
                             "https://premiumbanking.info/tbank/6")},
    "tbank_private_100": {**_TBANK_PRIVATE_SHARED,
                          "restaurants": _tbank_private_restaurants(
                              "https://premiumbanking.info/tbank/7"),
                          "service_cost": _free_on_conditions(
                              "https://premiumbanking.info/tbank/7")},
    # ----- ВТБ: Привилегия 1–4; Prime+ получает только общие банковские
    # условия ВТБ по карте/сбережениям, явно опубликованные на официальных
    # страницах ВТБ. Не переносить сюда уникальные сервисы без tier-source.
    "vtb_privilege_1": {**_VTB_PRIVILEGE_SHARED,
                        "entry_conditions": _VTB_PRIVILEGE_1_ENTRY,
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
    "vtb_prime_5": {
        "cashback": _VTB_CASHBACK,
        "deposits": _VTB_DEPOSITS,
        "cash_withdrawal": _VTB_PRIVILEGE_SHARED["cash_withdrawal"],
        "supreme": _VTB_PRIVILEGE_SHARED["supreme"],
    },
    "vtb_prime_6": {
        "cashback": _VTB_CASHBACK,
        "deposits": _VTB_DEPOSITS,
        "cash_withdrawal": _VTB_PRIVILEGE_SHARED["cash_withdrawal"],
        "supreme": _VTB_PRIVILEGE_SHARED["supreme"],
        "service_cost": _free_on_conditions("https://premiumbanking.info/vtb/6"),
    },
    "vtb_prime_7": {
        "cashback": _VTB_CASHBACK,
        "deposits": _VTB_DEPOSITS,
        "cash_withdrawal": _VTB_PRIVILEGE_SHARED["cash_withdrawal"],
        "supreme": _VTB_PRIVILEGE_SHARED["supreme"],
        "service_cost": _free_on_conditions("https://premiumbanking.info/vtb/7"),
    },
    "vtb_prime_8": {
        "cashback": _VTB_CASHBACK,
        "deposits": _VTB_DEPOSITS,
        "cash_withdrawal": _VTB_PRIVILEGE_SHARED["cash_withdrawal"],
        "supreme": _VTB_PRIVILEGE_SHARED["supreme"],
        "service_cost": _free_on_conditions("https://premiumbanking.info/vtb/8"),
    },
    # ----- Озон Банк -----
    "ozonbank_ultra_bronze": {
        **_OZONBANK_SHARED,
        "cash_withdrawal": _ozon_ultra_cash_withdrawal("3 000 000 ₽"),
    },
    "ozonbank_ultra_silver": {**_OZONBANK_SHARED,
                              "cash_withdrawal": _ozon_ultra_cash_withdrawal(
                                  "6 000 000 ₽"),
                              "service_cost": _free_on_conditions(
                                  "https://premiumbanking.info/ozon/2")},
    "ozonbank_ultra_gold": {**_OZONBANK_SHARED,
                            "cash_withdrawal": _ozon_ultra_cash_withdrawal(
                                "12 000 000 ₽"),
                            "service_cost": _free_on_conditions(
                                "https://premiumbanking.info/ozon/3")},
    "ozonbank_ultra_platinum": {**_OZONBANK_SHARED,
                                "cash_withdrawal": _ozon_ultra_cash_withdrawal(
                                    "30 000 000 ₽"),
                                "service_cost": _free_on_conditions(
                                    "https://premiumbanking.info/ozon/4")},
    # ----- Газпромбанк Premium -----
    "gpb_premium_1": {
        "entry_conditions": _GPB_PREMIUM_1_ENTRY,
        "deposits": _GPB_PREMIUM_DEPOSITS,
        "transfers_payments": _GPB_PREMIUM_TRANSFERS,
        "cash_withdrawal": _GPB_PREMIUM_CASH,
        "supreme": _GPB_PREMIUM_SUPREME,
    },
    "gpb_premium_2": {
        "entry_conditions": _GPB_PREMIUM_2_ENTRY,
        "deposits": _GPB_PREMIUM_DEPOSITS,
        "transfers_payments": _GPB_PREMIUM_TRANSFERS,
        "cash_withdrawal": _GPB_PREMIUM_CASH,
        "supreme": _GPB_PREMIUM_SUPREME,
        "service_cost": _free_on_conditions(
            "https://premiumbanking.info/gazprombank/2"),
    },
    "gpb_premium_3": {
        "deposits": _GPB_PREMIUM_DEPOSITS,
        "transfers_payments": _GPB_PREMIUM_TRANSFERS,
        "cash_withdrawal": _GPB_PREMIUM_CASH,
        "supreme": _GPB_PREMIUM_SUPREME,
        "service_cost": _free_on_conditions(
            "https://premiumbanking.info/gazprombank/3"),
    },
    # ----- Газпромбанк Private -----
    "gpb_private": {
        "service_cost": _free_on_conditions(
            "https://premiumbanking.info/gazprombank/4"),
        "deposits": _GPB_PRIVATE_DEPOSITS,
        "cashback": _fact(
            "Программа лояльности «Умный кэшбэк» (Газпром Бонус «Премиум»): "
            "до 15% + до 7% от ПС «Мир» в ресторанах, суммарно до 22%, "
            "лимит 40 000 ₽/мес",
            _GPB_BONUS,
            "Детализация именно для уровня Private не публикуется — "
            "указана премиальная версия программы банка"),
    },
    # ----- Альфа-Банк -----
    "alfa_only_1": {"entry_conditions": _ALFA_ONLY_1_ENTRY,
                    "addons": _ALFA_ADDONS_ABSENT,
                    "concierge": _ALFA_CONCIERGE_FACT,
                    "cashback": _ALFA_ONLY_CASHBACK,
                    "card_terms": _ALFA_ONLY_CARD_FREE,
                    "transfers_payments": _ALFA_ONLY_TRANSFERS,
                    "cash_withdrawal": _ALFA_ONLY_CASH_WITHDRAWAL,
                    "supreme": _ALFA_ONLY_SUPREME,
                    "deposits": _ALFA_ONLY_DEPOSITS},
    "alfa_only_2": {"addons": _ALFA_ADDONS_ABSENT,
                    "concierge": _ALFA_CONCIERGE_FACT,
                    "cashback": _ALFA_ONLY_CASHBACK,
                    "card_terms": _ALFA_ONLY_CARD_FREE,
                    "transfers_payments": _ALFA_ONLY_TRANSFERS,
                    "cash_withdrawal": _ALFA_ONLY_CASH_WITHDRAWAL,
                    "supreme": _ALFA_ONLY_SUPREME,
                    "deposits": _ALFA_ONLY_DEPOSITS,
                    "service_cost": _free_on_conditions(
                        "https://premiumbanking.info/alfabank/2")},
    "alfa_only_3": {"addons": _ALFA_ADDONS_ABSENT,
                    "concierge": _ALFA_CONCIERGE_FACT,
                    "cashback": _ALFA_ONLY_CASHBACK,
                    "card_terms": _ALFA_ONLY_CARD_FREE,
                    "transfers_payments": _ALFA_ONLY_TRANSFERS,
                    "cash_withdrawal": _ALFA_ONLY_CASH_WITHDRAWAL,
                    "supreme": _ALFA_ONLY_SUPREME,
                    "deposits": _ALFA_ONLY_DEPOSITS,
                    "service_cost": _free_on_conditions(
                        "https://premiumbanking.info/alfabank/3")},
    "alfa_only_4": {"addons": _ALFA_ADDONS_ABSENT,
                    "concierge": _ALFA_CONCIERGE_FACT,
                    "cashback": _ALFA_ONLY_CASHBACK,
                    "card_terms": _ALFA_ONLY_CARD_FREE,
                    "transfers_payments": _ALFA_ONLY_TRANSFERS,
                    "cash_withdrawal": _ALFA_ONLY_CASH_WITHDRAWAL,
                    "supreme": _ALFA_ONLY_SUPREME,
                    "deposits": _ALFA_ONLY_DEPOSITS,
                    "service_cost": _free_on_conditions(
                        "https://premiumbanking.info/alfabank/4")},
    "alfa_aclub": {
        "entry_conditions": _fact(
            "30 млн ₽ на счетах",
            _ALFA_ACLUB_OFFICIAL,
            "Актуальный единый порог входа в A-Club; прежнее разделение на "
            "60 млн ₽ для Москвы и 30 млн ₽ для регионов больше не применяется",
            date_checked="2026-07-21"),
        "lounge_access": _fact(
            "Бизнес-залы — безлимит",
            _PBI_ACLUB,
            "Fallback после недоступности официальной страницы A-Club"),
        "restaurants": _fact(
            "Рестораны — безлимит по 2 500 ₽",
            _PBI_ACLUB,
            "Fallback после недоступности официальной страницы A-Club"),
        "taxi": _fact(
            "Такси — 3 раза в месяц, 15 раз в год, до 5 000 ₽",
            _PBI_ACLUB,
            "Fallback после недоступности официальной страницы A-Club"),
        "insurance": _fact(
            "Страхование — €650 тыс, 90 дней, ассистанс Class Assistance",
            _PBI_ACLUB,
            "Fallback после недоступности официальной страницы A-Club"),
        "concierge": _fact(
            "Есть — консьерж-сервис PRIME",
            _PBI_ACLUB,
            "Не переносим консьерж-сервис Alfa Only в A-Club"),
        "ecosystem": _fact(
            "Консультации с юристом, бухгалтером; Альфа-Мобайл (50 ГБ, "
            "500 минут, 50 SMS); Alfa Only Lounge в SVO терминал C; "
            "А-Клуб Lounge в SVO терминал B; "
            "Закрытый винный клуб SimplePrivé — статус Gold, персональный "
            "сомелье и скидка 30% на основной ассортимент; "
            "Медицинский консьерж — организация обследований и лечения "
            "в лучших клиниках в России и за рубежом",
            _ALFA_ACLUB_OFFICIAL,
            "Постоянные привилегии A-Club: часть подтверждена ПБИ /alfabank/5; "
            "SimplePrivé и медицинский консьерж — по официальной странице A-Club "
            "(страница зарегистрирована, но при автоматической проверке может "
            "возвращать 403)"),
        "cashback": _fact(
            "не найдено",
            _PBI_ACLUB,
            "Постоянная программа кэшбэка A-Club в доступных источниках "
            "не подтверждена; временные акции не используются как тарифный факт"),
        "deposits": _ALFA_ACLUB_DEPOSITS,
        "card_terms": _fact(
            "не найдено",
            _PBI_ACLUB,
            "Карточные лимиты именно A-Club в доступных источниках не подтверждены; "
            "данные Alfa Only не переносятся"),
        "addons": _fact(
            "— (докупаемые опции A-Club в доступных источниках не заявлены)",
            _PBI_ACLUB,
            "Не переносим состав докупаемых опций Alfa Only"),
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
    "raif_premium_4": {"addons": _RAIF_ADDONS_ABSENT,
                       "service_cost": _free_on_conditions(
                           "https://premiumbanking.info/raiffeisen/4")},
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
