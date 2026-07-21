# -*- coding: utf-8 -*-
"""
Собственная сравнительная оценка пакетов (не рейтинг ПБИ).

Методика (полностью воспроизводима вручную, дублируется на листе
«Методика оценки» отчёта):

  1. По каждой категории привилегий из текста собранных данных извлекается
     ключевая метрика (число визитов в БЗ, % кэшбэка, ставка вклада,
     покрытие страховки и т.д.).
  2. Метрика переводится в балл 0–5 по пороговой таблице THRESHOLDS.
  3. Итоговый балл пакета = Σ (балл категории × вес категории), веса — в
     WEIGHTS (сумма = 1.0), результат в шкале 0–5.

Оценка ПБИ («ценность пакета в год») хранится отдельным справочным полем
и в расчёте НЕ участвует.

Веса и пороги — конфигурация: меняйте без правки кода расчёта.
"""

import re

from scanner.merge import field_value
from scanner.sources import NOT_FOUND

# Веса категорий (сумма = 1.0)
WEIGHTS = {
    "lounge_access": 0.20,
    "cashback": 0.20,
    "deposits": 0.15,
    "taxi_restaurants": 0.10,
    "insurance": 0.10,
    "concierge": 0.10,
    "ecosystem": 0.10,
    "auto": 0.05,
}

# Пороговые таблицы: список (минимум метрики, балл), проверяется сверху вниз
THRESHOLDS = {
    # визитов в бизнес-залы в месяц (безлимит = 5 сразу)
    "lounge_visits": [(8, 4), (4, 3), (2, 2), (1, 1)],
    # максимальный % кэшбэка
    "cashback_pct": [(10, 5), (7, 4), (5, 3), (3, 2), (0.1, 1)],
    # максимальная ставка вклада/НС, % годовых
    "deposit_rate": [(14, 5), (12, 4), (9, 3), (5, 2), (0.1, 1)],
    # совместимый индекс такси/ресторанов в месяц: берём максимум по отдельным
    # категориям, а не сумму поездок и ресторанных чеков
    "taxi_rest_count": [(10, 4), (4, 3), (2, 2), (1, 1)],
    # число экосистемных опций/подписок в пакете
    "ecosystem_count": [(6, 5), (4, 4), (2, 3), (1, 2)],
}

# Покрытие страховки ВЗР -> (описание, балл)
INSURANCE_RULES = [
    (r"€?\$?\s*1[\s/]*млн|млн\s*[€$]", "покрытие ~1 млн", 5),
    (r"500\s*тыс", "покрытие ~500 тыс", 4),
    (r"1[05]0\s*тыс|100\s*тыс", "покрытие ~100–150 тыс", 3),
    (r"[3-9]0\s*тыс", "покрытие ~30–90 тыс", 2),
]

NEGATION_MARKERS = ["не предусмотрен", "не входит", "нет —", "нет,", "нет ("]
UNLIMITED_MARKERS = ["безлимит", "без ограничений", "не ограничен"]


def _threshold_score(value: float, table_key: str) -> int:
    for minimum, score in THRESHOLDS[table_key]:
        if value >= minimum:
            return score
    return 0


def _is_negated(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in NEGATION_MARKERS)


def _max_number(text: str, pattern: str):
    matches = re.findall(pattern, text)
    values = []
    for m in matches:
        try:
            values.append(float(m.replace(",", ".")))
        except ValueError:
            continue
    return max(values) if values else None


# ---------- экстракторы метрик: (описание метрики, балл 0–5) ----------

def _score_lounge(text: str):
    low = text.lower()
    if any(m in low for m in UNLIMITED_MARKERS):
        return "безлимитные визиты", 5
    visits = _max_number(low, r"(\d+)\s*(?:бз\s*)?в мес")
    if visits is None:
        visits = _max_number(low, r"\((\d+)\s*бз\)")
    if visits is not None:
        return f"{int(visits)} визит(ов)/мес", _threshold_score(visits, "lounge_visits")
    return "упомянуты без числа визитов", 1


def _score_concierge(text: str):
    if _is_negated(text):
        return "нет", 0
    return "есть", 5


def _score_cashback(text: str):
    scoring_text = re.sub(r"супер[^\n.;|]{0,60}?до\s*\d+(?:[.,]\d+)?\s*%",
                          "", text, flags=re.IGNORECASE)
    pct = _max_number(scoring_text, r"(\d+(?:[.,]\d+)?)\s*%")
    if pct is not None:
        return f"до {pct:g}%", _threshold_score(pct, "cashback_pct")
    if "обмен" in text.lower() and "бонус" in text.lower():
        return "только повышенный курс обмена бонусов", 2
    return "механика без ставки", 1


def _score_deposits(text: str):
    rate = _max_number(text, r"(\d+(?:[.,]\d+)?)\s*%")
    if rate is not None:
        return f"до {rate:g}% годовых", _threshold_score(rate, "deposit_rate")
    return "спецусловия без опубликованной ставки", 1


def _score_insurance(text: str):
    if _is_negated(text):
        return "не предусмотрена", 0
    low = text.lower()
    for pattern, description, score in INSURANCE_RULES:
        if re.search(pattern, low):
            return _insurance_summary(text) or description, score
    return "есть, покрытие не распознано", 1


def _score_auto(text: str):
    low = text.lower()
    if "опция" in low and "всегда включ" not in low:
        return "опция на выбор, не гарантированно включена", 1
    score = 3
    details = ["опция есть"]
    if "помощь на дорог" in low:
        score += 1
        details.append("помощь на дорогах")
    if re.search(r"(кешбэк|кэшбэк).{0,30}(дорог|парковк)", low):
        score += 1
        details.append("кэшбэк за дороги/парковки")
    return ", ".join(details), min(score, 5)


def _score_taxi_rest(text: str):
    low = text.lower()
    if any(m in low for m in UNLIMITED_MARKERS):
        return "безлимит", 5
    counts = [int(n) for n in re.findall(r"(\d+)\s*(?:в мес|/мес)", low)]
    if counts:
        count = max(counts)
        note = "максимум по такси/ресторанам без суммирования"
        if "опция" in low and "всегда включ" not in low:
            note += "; опция на выбор"
        return f"{count} в месяц ({note})", _threshold_score(
            count, "taxi_rest_count")
    return "есть без числа компенсаций", 1


def _insurance_summary(text: str) -> str:
    """Краткое точное отображение условий для методики и HTML."""
    public = re.sub(r"\s*\[[^\]]+\]", "", text)
    amount = re.search(
        r"((?:[$€]\s*)?\d+(?:[.,]\d+)?(?:/\d+(?:[.,]\d+)?)?\s*(?:млн|тыс)?|"
        r"(?:[$€]\s*)\d+\s*/\s*\d+\s*млн)",
        public,
        flags=re.IGNORECASE,
    )
    days = re.search(r"(?:до\s*)?\d+\s*(?:дн|дней|дня)", public,
                     flags=re.IGNORECASE)
    assistance = re.search(r"ассистанс\s+[^|;,.]+", public, flags=re.IGNORECASE)
    parts = []
    if amount:
        parts.append(amount.group(0).strip())
    if days:
        parts.append(days.group(0).strip())
    if assistance:
        parts.append(assistance.group(0).strip())
    return " · ".join(parts)


def _score_ecosystem(text: str):
    count = len(re.findall(r"опция «|подписк|прайм|okko|плюс", text.lower()))
    if count:
        return f"{count} опций/подписок упомянуто", _threshold_score(
            count, "ecosystem_count")
    return "есть, состав не распознан", 1


SCORERS = {
    "lounge_access": _score_lounge,
    "concierge": _score_concierge,
    "cashback": _score_cashback,
    "deposits": _score_deposits,
    "insurance": _score_insurance,
    "auto": _score_auto,
    "taxi_restaurants": _score_taxi_rest,
    "ecosystem": _score_ecosystem,
}


def score_tier(fields: dict) -> dict:
    """
    Возвращает {"total": float, "breakdown": {category: {"metric", "score",
    "weight", "contribution"}}}. Категория с "не найдено" получает 0.
    """
    breakdown = {}
    total = 0.0
    for category, weight in WEIGHTS.items():
        if category == "taxi_restaurants":
            text = _combined_taxi_rest_text(fields)
        else:
            text = field_value(fields.get(category, NOT_FOUND))
        if text == NOT_FOUND:
            metric, score = "не найдено", 0
        elif text.strip().startswith("—"):
            metric, score = "отсутствует по условиям тира", 0
        else:
            metric, score = SCORERS[category](text)
        contribution = round(score * weight, 3)
        total += contribution
        breakdown[category] = {
            "metric": metric,
            "score": score,
            "weight": weight,
            "contribution": contribution,
        }
    return {"total": round(total, 2), "breakdown": breakdown}


def _combined_taxi_rest_text(fields: dict) -> str:
    split_values = [
        field_value(fields.get("taxi", NOT_FOUND)),
        field_value(fields.get("restaurants", NOT_FOUND)),
    ]
    present = [v for v in split_values if v != NOT_FOUND]
    if present:
        return " ; ".join(present)
    return field_value(fields.get("taxi_restaurants", NOT_FOUND))


METHODOLOGY_TEXT = [
    "Итоговый балл пакета = Σ (балл категории 0–5 × вес категории); шкала 0–5.",
    "Балл категории получается из метрики, извлечённой из собранных данных, "
    "по пороговым таблицам ниже. Всё воспроизводимо вручную: метрика и балл "
    "каждой категории каждого тира показаны в таблице разбивки.",
    "Категория «не найдено» получает 0 — отсутствие данных снижает балл, "
    "это стимул закрывать пробелы в данных, а не оценка «в пользу» банка.",
    "Оценка ПБИ («ценность пакета в год») — справочное поле, в расчёте "
    "итогового балла НЕ участвует.",
    "Категория «Карты» (тип носителя, лимиты переводов/снятия, выпуск) — "
    "справочная, в итоговый балл не входит: карточные лимиты — "
    "инфраструктурный параметр, а не привилегия; веса категорий не менялись.",
    "Такси и рестораны теперь хранятся раздельно. Для обратной совместимости "
    "старый вес 0,10 сохранён как объединённый индекс: скоринг берёт максимум "
    "месячного количества по такси или ресторанам, а не складывает поездки и "
    "ресторанные чеки. Опции на выбор помечаются отдельно и не считаются "
    "одновременно получаемыми привилегиями.",
    "Вес «Автоуслуги» сохранён для совместимости. Если авто найдено только как "
    "опция на выбор, категория получает консервативный балл и требует "
    "продуктового решения по будущим весам.",
    "",
    "Правила слияния источников: верифицированный вручную факт (с ссылкой на "
    "первоисточник) > структурированные данные > цитаты-сниппеты; внутри "
    "одного качества приоритет: официальный сайт банка > premiumbanking.info "
    "> Banki.ru > Sravni.ru > Bankiros. Значения всех источников сохраняются; "
    "расхождение чисел между источниками помечается в колонке «Расхождение».",
]
