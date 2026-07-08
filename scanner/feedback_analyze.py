# -*- coding: utf-8 -*-
"""Local-first Voice of Customer analysis."""

import re
from collections import Counter, defaultdict

from scanner.feedback_models import FeedbackAnalysis

TOPIC_TAXONOMY = {
    "персональный менеджер": ["персональн", "личный менеджер", "менеджер"],
    "поддержка": ["поддержк", "900", "чат", "горяч", "оператор"],
    "скорость обслуживания": ["долго", "ждал", "ожидан", "быстро", "медленно", "срок"],
    "инвестиции": ["инвест", "портфель", "акци", "облигац"],
    "брокерское обслуживание": ["брокер", "иис", "брокерск"],
    "вклады": ["вклад", "накопительн", "ставк", "процент"],
    "обмен валют": ["курс", "валют", "обмен"],
    "бонусы Спасибо": ["спасибо", "бонус"],
    "мобильное приложение": ["приложен", "сбербанк онлайн", "сбол", "app"],
    "бизнес-залы": ["бизнес-зал", "бизнес зал", "lounge", "лаунж"],
    "страховка": ["страхов", "полис", "взр"],
    "консьерж": ["консьерж", "ассистент"],
    "трансферы": ["трансфер"],
    "рестораны": ["ресторан", "кафе"],
    "такси": ["такси"],
    "премиальные карты": ["премиальн", "карта", "металл", "visa", "mastercard", "мир"],
    "условия бесплатного обслуживания": ["бесплатн", "услов", "порог", "остаток"],
    "стоимость обслуживания": ["стоимость", "плата", "комисс", "руб/мес", "₽"],
    "офис": ["офис", "отделение", "доп офис"],
    "цифровые сервисы": ["цифров", "домклик", "сберid", "онлайн"],
    "безопасность": ["безопас", "мошен", "блокиров", "доступ"],
    "привилегии": ["привилег", "опци", "пакет", "фитмост"],
    "персональные предложения": ["персональн", "предложен", "индивидуальн"],
}

POSITIVE_WORDS = [
    "отлично", "хорошо", "удобно", "быстро", "помог", "доволен", "спасибо",
    "понрав", "качественно", "оперативно", "лучше", "комфортно", "выгод",
]
STRONG_POSITIVE_WORDS = ["восторг", "прекрасно", "идеально", "лучший", "супер"]
NEGATIVE_WORDS = [
    "плохо", "долго", "отказ", "не работает", "обман", "навяз", "комиссия",
    "списал", "хам", "не дозвон", "жалоб", "проблем", "разочар", "бесполез",
    "не помог", "ошибка", "не предупред",
]
STRONG_NEGATIVE_WORDS = ["ужас", "кошмар", "никогда", "абсурд", "бессили", "говнобанк"]

COMPLAINT_MARKERS = NEGATIVE_WORDS + STRONG_NEGATIVE_WORDS
WISH_MARKERS = [
    "хотелось бы", "нужно добавить", "не хватает", "сделайте", "добавьте",
    "было бы удобно", "нужен", "нужна", "улучшить", "изменить",
]
EMOTION_MARKERS = {
    "раздражение": ["раздраж", "злит", "бесит", "достал"],
    "разочарование": ["разочар", "ожидал", "не оправдал"],
    "доверие": ["надежн", "довер", "уверен"],
    "благодарность": ["спасибо", "благодар"],
    "восторг": ["восторг", "супер", "прекрасно", "идеально"],
    "недовольство": ["недовол", "плохо", "проблем", "жалоб"],
    "удивление": ["удив", "внезапно", "неожидан"],
}


def analyze_reviews(reviews: list) -> dict:
    return {review.review_id: analyze_review(review).to_dict() for review in reviews}


def analyze_review(review) -> FeedbackAnalysis:
    text = " ".join([review.title or "", review.pros or "", review.cons or "", review.text or ""])
    low = text.lower()
    sentiment_score = max(-1.0, min(1.0, _rating_score(review.rating) + _keyword_score(low)))
    sentiment = _sentiment_label(sentiment_score)
    topics = _topics(low)
    complaint_phrases = _phrases(text, COMPLAINT_MARKERS)
    wish_phrases = _phrases(text, WISH_MARKERS)
    advantages = _phrases(" ".join([review.pros or "", review.text or ""]), POSITIVE_WORDS)
    disadvantages = _phrases(" ".join([review.cons or "", review.text or ""]), COMPLAINT_MARKERS)
    emotions = _emotions(low, sentiment)
    emotion_score = _emotion_score(low)
    return FeedbackAnalysis(
        review_id=review.review_id,
        sentiment=sentiment,
        sentiment_score=round(sentiment_score, 3),
        sentiment_index=round((sentiment_score + 1) * 50, 1),
        emotions=emotions,
        topics=topics,
        advantages=advantages,
        disadvantages=disadvantages,
        complaint_phrases=complaint_phrases,
        wish_phrases=wish_phrases,
        emotion_score=emotion_score,
        is_complaint=bool(complaint_phrases) or "негатив" in sentiment.lower(),
        is_wish=bool(wish_phrases),
    )


def build_insights(reviews: list, analyses: dict, prev_scan: dict = None) -> dict:
    review_by_id = {review.review_id: review for review in reviews}
    advantages = _rank_phrases(reviews, analyses, "advantages")
    disadvantages = _rank_phrases(reviews, analyses, "disadvantages")
    wishes = _rank_phrases(reviews, analyses, "wish_phrases")
    topic_metrics = _topic_metrics(reviews, analyses, prev_scan)
    repeated = [
        {"topic": topic, **metric}
        for topic, metric in topic_metrics.items()
        if metric["reviews_count"] >= 2 and metric["source_count"] >= 1
    ]
    new_problems = [
        {"topic": topic, **metric}
        for topic, metric in topic_metrics.items()
        if metric["delta"] > 0 and metric["negative_share"] > 0
    ]
    resolved = []
    prev_topics = (prev_scan or {}).get("insights", {}).get("topic_metrics", {})
    for topic, prev_metric in prev_topics.items():
        if topic not in topic_metrics and prev_metric.get("negative_share", 0) > 0:
            resolved.append({"topic": topic, "previous_count": prev_metric.get("reviews_count", 0)})
    return {
        "advantages": advantages,
        "disadvantages": disadvantages,
        "wishes": wishes,
        "repeated_problems": sorted(repeated, key=lambda x: (-x["criticality_index"], x["topic"])),
        "new_problems": sorted(new_problems, key=lambda x: (-x["delta"], x["topic"])),
        "resolved_problems": resolved,
        "topic_metrics": topic_metrics,
        "record_count": len(review_by_id),
    }


def emerging_topics(reviews: list, analyses: dict, limit: int = 20) -> list:
    known = set(TOPIC_TAXONOMY)
    phrase_reviews = defaultdict(set)
    for review in reviews:
        analysis = analyses.get(review.review_id, {})
        if not (analysis.get("is_complaint") or analysis.get("is_wish")):
            continue
        for phrase in re.findall(r"[А-Яа-яA-Za-z][А-Яа-яA-Za-z -]{4,40}", review.text):
            norm = " ".join(phrase.lower().split())
            if len(norm) < 5 or any(topic in norm for topic in known):
                continue
            phrase_reviews[norm].add(review.review_id)
    ranked = [(p, len(ids)) for p, ids in phrase_reviews.items() if len(ids) >= 5]
    return [k for k, _ in sorted(ranked, key=lambda x: (-x[1], x[0]))[:limit]]


def _rating_score(rating):
    if rating is None:
        return 0.0
    try:
        rating = float(rating)
    except (TypeError, ValueError):
        return 0.0
    if rating <= 1:
        return -0.8
    if rating <= 2:
        return -0.5
    if rating >= 5:
        return 0.8
    if rating >= 4:
        return 0.5
    return 0.0


def _keyword_score(low: str) -> float:
    pos = sum(1 for word in POSITIVE_WORDS if word in low)
    pos += 2 * sum(1 for word in STRONG_POSITIVE_WORDS if word in low)
    neg = sum(1 for word in NEGATIVE_WORDS if word in low)
    neg += 2 * sum(1 for word in STRONG_NEGATIVE_WORDS if word in low)
    return max(-0.8, min(0.8, (pos - neg) * 0.16))


def _sentiment_label(score: float) -> str:
    if score <= -0.6:
        return "Очень негативный"
    if score <= -0.2:
        return "Негативный"
    if score >= 0.6:
        return "Очень позитивный"
    if score >= 0.2:
        return "Позитивный"
    return "Нейтральный"


def _topics(low: str) -> list:
    topics = []
    for topic, markers in TOPIC_TAXONOMY.items():
        if any(marker in low for marker in markers):
            topics.append(topic)
    return topics or ["прочее"]


def _phrases(text: str, markers: list) -> list:
    result = []
    sentences = re.split(r"(?<=[.!?])\s+|\n", text)
    for sentence in sentences:
        low = sentence.lower()
        if any(marker in low for marker in markers):
            cleaned = sentence.strip()[:280]
            if cleaned and cleaned not in result:
                result.append(cleaned)
        if len(result) >= 3:
            break
    return result


def _emotions(low: str, sentiment: str) -> list:
    found = []
    for emotion, markers in EMOTION_MARKERS.items():
        if any(marker in low for marker in markers):
            found.append(emotion)
    if not found:
        if "негатив" in sentiment.lower():
            found.append("недовольство")
        elif "позитив" in sentiment.lower():
            found.append("доверие")
    return found


def _emotion_score(low: str) -> float:
    score = sum(low.count(marker) for marker in ["!", "ужас", "кошмар", "никогда", "совсем", "крайне", "очень"]) * 0.15
    caps = len(re.findall(r"[А-ЯA-Z]{3,}", low))
    return round(min(1.0, score + caps * 0.1), 3)


def _rank_phrases(reviews: list, analyses: dict, key: str) -> list:
    counts = Counter()
    examples = {}
    review_by_id = {r.review_id: r for r in reviews}
    for rid, analysis in analyses.items():
        for phrase in analysis.get(key, []):
            topic = _short_phrase(phrase)
            counts[topic] += 1
            examples.setdefault(topic, {
                "quote": phrase[:320],
                "source": review_by_id.get(rid).source_name if rid in review_by_id else "",
                "url": review_by_id.get(rid).url if rid in review_by_id else "",
            })
    return [
        {"item": item, "count": count, "example": examples.get(item, {})}
        for item, count in counts.most_common(20)
    ]


def _short_phrase(phrase: str) -> str:
    text = re.sub(r"\s+", " ", phrase).strip()
    return text[:120]


def _topic_metrics(reviews: list, analyses: dict, prev_scan: dict = None) -> dict:
    prev_counts = (prev_scan or {}).get("trends", {}).get("topic_counts", {})
    metrics = {}
    for topic in sorted({t for a in analyses.values() for t in a.get("topics", [])}):
        topic_reviews = [
            review for review in reviews
            if topic in analyses.get(review.review_id, {}).get("topics", [])
        ]
        if not topic_reviews:
            continue
        sentiments = [analyses[r.review_id].get("sentiment", "Нейтральный") for r in topic_reviews]
        negative = sum(1 for s in sentiments if "негатив" in s.lower())
        positive = sum(1 for s in sentiments if "позитив" in s.lower())
        ratings = [r.rating for r in topic_reviews if r.rating is not None]
        reviews_count = len(topic_reviews)
        negative_share = negative / reviews_count
        positive_share = positive / reviews_count
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else ""
        criticality = round(reviews_count * (0.6 * negative_share + 0.4 * (1 - positive_share)), 3)
        metrics[topic] = {
            "reviews_count": reviews_count,
            "average_rating": avg_rating,
            "negative_share": round(negative_share, 3),
            "positive_share": round(positive_share, 3),
            "criticality_index": criticality,
            "delta": reviews_count - int(prev_counts.get(topic, 0)),
            "source_count": len({r.source_id for r in topic_reviews}),
        }
    return metrics
