# -*- coding: utf-8 -*-
"""Product improvement recommendations from Voice of Customer analysis."""

import hashlib
from datetime import datetime

from scanner.feedback_models import FeedbackSuggestion

MIN_STRONG_SUPPORT = 3
MIN_RECOMMENDATION_SUPPORT = 2


def build_suggestions(reviews: list, analyses: dict, scan_dt: str) -> list:
    by_topic = {}
    review_by_id = {review.review_id: review for review in reviews}
    for review in reviews:
        analysis = analyses.get(review.review_id, {})
        if review.record_type == "market_signal":
            continue
        if not (analysis.get("is_complaint") or analysis.get("is_wish")):
            continue
        for topic in analysis.get("topics", ["прочее"]):
            by_topic.setdefault(topic, []).append(review.review_id)

    suggestions = []
    total_reviews = max(1, len([r for r in reviews if r.record_type == "review"]))
    for topic, review_ids in sorted(by_topic.items(), key=lambda x: (-len(x[1]), x[0])):
        support = [review_by_id[rid] for rid in review_ids if rid in review_by_id]
        support_count = len(support)
        if support_count < MIN_RECOMMENDATION_SUPPORT:
            continue
        source_count = len({r.source_id for r in support})
        negative_count = sum(
            1 for rid in review_ids
            if "негатив" in analyses.get(rid, {}).get("sentiment", "").lower())
        mass_score = min(1.0, support_count / total_reviews)
        negative_score = negative_count / max(1, support_count)
        repeatability_score = min(1.0, support_count / MIN_STRONG_SUPPORT)
        recency_score = _recency_score(support, scan_dt)
        source_diversity_score = min(1.0, source_count / 3)
        priority_score = (
            0.30 * mass_score
            + 0.25 * negative_score
            + 0.20 * repeatability_score
            + 0.15 * source_diversity_score
            + 0.10 * recency_score
        )
        suggestions.append(FeedbackSuggestion(
            suggestion_id=_suggestion_id(topic),
            title=_title(topic),
            basis=_basis(topic, support_count, source_count, negative_count),
            affected_categories=sorted({t for rid in review_ids for t in analyses.get(rid, {}).get("topics", [])}),
            problem_description=_problem_description(topic, support, support_count),
            recommended_change=_recommended_change(topic, support_count),
            expected_effect=_expected_effect(topic),
            quotes_with_sources=_quotes(support, analyses),
            supporting_review_ids=review_ids[:20],
            support_count=support_count,
            source_count=source_count,
            mass_score=round(mass_score, 3),
            negative_score=round(negative_score, 3),
            recency_score=round(recency_score, 3),
            repeatability_score=round(repeatability_score, 3),
            source_diversity_score=round(source_diversity_score, 3),
            priority=_priority(priority_score, support_count),
            priority_score=round(priority_score, 3),
        ).to_dict())
    return suggestions


def _suggestion_id(topic: str) -> str:
    digest = hashlib.sha1(topic.encode("utf-8")).hexdigest()[:10]
    return f"sug_{digest}"


def _title(topic: str) -> str:
    return f"Изменить клиентский путь: {topic}"


def _basis(topic: str, support_count: int, source_count: int, negative_count: int) -> str:
    confidence = "Предварительный вывод" if support_count < MIN_STRONG_SUPPORT else "Подтверждённый повторяемый сигнал"
    return (f"{confidence}: тема «{topic}» встречается в {support_count} отзыв(ах), "
            f"источников: {source_count}, негативных упоминаний: {negative_count}.")


def _problem_description(topic: str, support: list, support_count: int) -> str:
    if support_count < MIN_STRONG_SUPPORT:
        return (f"Данных пока недостаточно для окончательного вывода по теме «{topic}». "
                "Сигнал нужно мониторить и подтверждать новыми отзывами.")
    return (f"Клиенты повторно указывают на проблему в теме «{topic}». "
            "Негатив возникает из-за несоответствия ожиданий премиального сервиса фактическому опыту.")


def _recommended_change(topic: str, support_count: int) -> str:
    mapping = {
        "условия бесплатного обслуживания": "Сделать условия бесплатного обслуживания и пороги входа понятнее в приложении, на сайте и в коммуникации менеджеров.",
        "стоимость обслуживания": "Добавить предварительное уведомление о списании платы и причину списания с расшифровкой условий.",
        "поддержка": "Сократить время ответа премиальной поддержки и ввести контроль SLA для обращений премиальных клиентов.",
        "персональный менеджер": "Пересмотреть стандарты работы персональных менеджеров: скорость ответа, ответственность за решение и escalation path.",
        "мобильное приложение": "Упростить цифровой путь подключения/управления привилегиями в приложении.",
        "бизнес-залы": "Проверить достаточность лимитов и прозрачность правил прохода в бизнес-залы.",
        "бонусы Спасибо": "Сделать механику начисления/обмена бонусов прозрачнее и показать лимиты до операции.",
        "инвестиции": "Усилить качество инвестиционного сопровождения и раскрытие рисков.",
        "брокерское обслуживание": "Развести премиальный банковский и брокерский сервисы с понятным ответственным менеджером.",
    }
    default = f"Провести разбор клиентского пути по теме «{topic}» и устранить повторяющиеся причины негативных отзывов."
    suffix = " Вывод предварительный: сначала накопить больше отзывов." if support_count < MIN_STRONG_SUPPORT else ""
    return mapping.get(topic, default) + suffix


def _expected_effect(topic: str) -> str:
    return (f"Снижение негативных отзывов по теме «{topic}», рост доли позитивного sentiment, "
            "меньше повторных обращений и выше воспринимаемая ценность премиального обслуживания.")


def _quotes(support: list, analyses: dict) -> list:
    quotes = []
    for review in support[:5]:
        analysis = analyses.get(review.review_id, {})
        phrase = ""
        for key in ("complaint_phrases", "wish_phrases", "disadvantages"):
            values = analysis.get(key, [])
            if values:
                phrase = values[0]
                break
        phrase = phrase or review.text[:260]
        quotes.append({
            "quote": phrase[:360],
            "source": review.source_name,
            "url": review.url,
            "review_id": review.review_id,
        })
    return quotes


def _priority(score: float, support_count: int) -> str:
    if support_count < MIN_STRONG_SUPPORT:
        return "Низкий"
    if score >= 0.65:
        return "Высокий"
    if score >= 0.4:
        return "Средний"
    return "Низкий"


def _recency_score(reviews: list, scan_dt: str) -> float:
    scan_date = _parse_date(scan_dt)
    if not scan_date:
        return 0.5
    scores = []
    for review in reviews:
        review_date = _parse_date(review.published_at or review.date)
        if not review_date:
            scores.append(0.5)
            continue
        age_days = max(0, (scan_date - review_date).days)
        scores.append(max(0.0, 1.0 - age_days / 180))
    return sum(scores) / max(1, len(scores))


def _parse_date(value: str):
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19] if "T" in fmt else value[:10], fmt)
        except ValueError:
            continue
    return None
