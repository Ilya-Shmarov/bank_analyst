# -*- coding: utf-8 -*-
"""Static Voice of Customer dashboard."""

import html
import json
from pathlib import Path


def build_feedback_dashboard(history: dict, output_path: Path) -> dict:
    scan = history["scans"][-1] if history.get("scans") else {
        "date": "", "reviews": [], "analyses": {}, "suggestions": [],
        "trends": {}, "insights": {}, "meta": {}}
    scan = _with_merged_source_stats(scan, history)
    data_json = json.dumps(_dashboard_data(scan), ensure_ascii=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_html(scan, data_json), encoding="utf-8")
    return {"output": str(output_path), "reviews": len(scan.get("reviews", []))}


def _with_merged_source_stats(scan: dict, history: dict) -> dict:
    merged = {}
    for item in history.get("scans", []):
        for stat in item.get("meta", {}).get("source_stats", []):
            source_id = stat.get("source_id")
            if source_id:
                merged[source_id] = stat
    if not merged:
        return scan
    result = dict(scan)
    meta = dict(scan.get("meta", {}))
    meta["source_stats"] = list(merged.values())
    result["meta"] = meta
    return result


def _dashboard_data(scan: dict) -> dict:
    return {
        "date": scan.get("date", ""),
        "reviews": scan.get("reviews", []),
        "analyses": scan.get("analyses", {}),
        "trends": scan.get("trends", {}),
        "insights": scan.get("insights", {}),
        "suggestions": scan.get("suggestions", []),
        "meta": scan.get("meta", {}),
    }


def _html(scan: dict, data_json: str) -> str:
    reviews = scan.get("reviews", [])
    analyses = scan.get("analyses", {})
    insights = scan.get("insights", {})
    trends = scan.get("trends", {})
    source_stats = scan.get("meta", {}).get("source_stats", [])
    ratings = [r.get("rating") for r in reviews if r.get("rating") is not None]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else "—"
    sentiment_index = _avg_sentiment_index(analyses)
    review_sources = len({r.get("source_id") for r in reviews})
    market_signals = sum(1 for r in reviews if r.get("record_type") == "market_signal")
    customer_reviews = len(reviews) - market_signals

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Voice of Customer: Premium Banking</title>
  <style>
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; color:#17212b; background:#f3f5f6; }}
    header {{ background:#0f3d2e; color:white; padding:30px 42px; }}
    main {{ max-width:1240px; margin:0 auto; padding:24px; }}
    h1 {{ margin:0 0 6px; font-size:30px; letter-spacing:0; }}
    h2 {{ margin:30px 0 12px; font-size:21px; letter-spacing:0; }}
    h3 {{ margin:0 0 8px; font-size:17px; }}
    .lead {{ max-width:900px; color:#dbe7e1; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }}
    .metric,.card,.notice {{ background:white; border:1px solid #d8dee4; border-radius:8px; padding:16px; }}
    .metric b {{ display:block; font-size:28px; margin-top:4px; }}
    .muted {{ color:#5b6875; }}
    .rec-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); gap:14px; }}
    details {{ background:white; border:1px solid #d8dee4; border-radius:8px; margin:10px 0; }}
    summary {{ cursor:pointer; padding:13px 16px; font-weight:700; }}
    details[open] summary {{ border-bottom:1px solid #e5e7eb; }}
    .review-list {{ display:grid; gap:10px; padding:12px 16px 16px; }}
    .review-card {{ border:1px solid #e5e7eb; border-radius:7px; padding:12px; background:#fbfcfd; }}
    .review-card h4 {{ margin:0 0 6px; font-size:15px; }}
    .review-meta {{ color:#5b6875; font-size:13px; margin-bottom:8px; }}
    .review-text {{ margin:0; line-height:1.45; }}
    .chips {{ margin-top:8px; display:flex; flex-wrap:wrap; gap:6px; }}
    .chip {{ background:#eef3f1; border-radius:5px; padding:2px 7px; font-size:12px; color:#334155; }}
    .priority {{ display:inline-block; padding:3px 8px; border-radius:5px; background:#eaf2ed; font-weight:700; }}
    table {{ width:100%; border-collapse:collapse; background:white; border:1px solid #d8dee4; }}
    th,td {{ text-align:left; vertical-align:top; padding:10px; border-bottom:1px solid #e5e7eb; }}
    th {{ background:#eaf2ed; }}
    .bar {{ height:10px; background:#2f855a; border-radius:6px; min-width:4px; }}
    .quote {{ border-left:3px solid #2f855a; padding-left:10px; margin-top:8px; color:#334155; }}
    .warn {{ background:#fff7ed; border-color:#fed7aa; }}
  </style>
</head>
<body>
  <header>
    <h1>Voice of Customer: Premium Banking Feedback Intelligence</h1>
    <div class="lead">Дата скана: {_esc(scan.get('date', '') or 'нет данных')}. Итоговый отчет фокусируется на продуктовых рекомендациях, подтвержденных отзывами и внешними сигналами.</div>
  </header>
  <main>
    {_empty_note(scan)}
    <section class="grid">
      <div class="metric"><span>Записей всего</span><b>{len(reviews)}</b></div>
      <div class="metric"><span>Клиентских отзывов</span><b>{customer_reviews}</b></div>
      <div class="metric"><span>Market signals</span><b>{market_signals}</b></div>
      <div class="metric"><span>Источников с данными</span><b>{review_sources}</b></div>
      <div class="metric"><span>Средний рейтинг</span><b>{avg_rating}</b></div>
      <div class="metric"><span>Sentiment index</span><b>{sentiment_index}</b></div>
    </section>

    <h2>Рекомендации по развитию премиального обслуживания</h2>
    {_recommendations(scan)}

    <h2>Фактическая база</h2>
    {_review_evidence(scan)}

    <h2>Sentiment Dashboard</h2>
    {_sentiment_table(trends.get('sentiment_counts', {}))}

    <h2>TOP преимуществ</h2>
    {_rank_table(insights.get('advantages', []), 'Преимущество')}

    <h2>TOP недостатков</h2>
    {_rank_table(insights.get('disadvantages', []), 'Недостаток')}

    <h2>TOP пожеланий</h2>
    {_rank_table(insights.get('wishes', []), 'Пожелание')}

    <h2>Heatmap тем</h2>
    {_topic_heatmap(insights.get('topic_metrics', {}))}

    <h2>Повторяющиеся и новые проблемы</h2>
    {_problems(insights)}

    <h2>Статус источников</h2>
    {_source_table(source_stats)}
  </main>
  <script id="feedback-data" type="application/json">{_esc(data_json)}</script>
</body>
</html>
"""


def _recommendations(scan: dict) -> str:
    suggestions = scan.get("suggestions", [])
    reviews = {review.get("review_id"): review for review in scan.get("reviews", [])}
    analyses = scan.get("analyses", {})
    if not suggestions:
        return "<section class='notice warn'><b>Рекомендаций пока нет</b><br>Недостаточно клиентских отзывов для продуктовых выводов. Market signals отображаются в статистике, но не превращаются в гипотезы без клиентского подтверждения.</section>"
    cards = []
    for sug in suggestions[:12]:
        support_ids = sug.get("supporting_review_ids", [])
        support_cards = "".join(
            _review_card(reviews[rid], analyses.get(rid, {}))
            for rid in support_ids
            if rid in reviews
        )
        if not support_cards:
            support_cards = "".join(
                f"<div class='quote'>{_esc(q.get('quote', ''))}<br><span class='muted'>{_esc(q.get('source', ''))} · {_link(q.get('url', ''))}</span></div>"
                for q in sug.get("quotes_with_sources", [])[:5])
        evidence = (
            f"<details><summary>Показать подтверждающие отзывы ({len(support_ids)})</summary>"
            f"<div class='review-list'>{support_cards}</div></details>"
        )
        cards.append(
            "<section class='card'>"
            f"<span class='priority'>{_esc(sug.get('priority', ''))}</span>"
            f"<h3>{_esc(sug.get('title', ''))}</h3>"
            f"<p><b>Основание:</b> {_esc(sug.get('basis', ''))}</p>"
            f"<p><b>Проблема:</b> {_esc(sug.get('problem_description', ''))}</p>"
            f"<p><b>Что изменить:</b> {_esc(sug.get('recommended_change', ''))}</p>"
            f"<p><b>Ожидаемый эффект:</b> {_esc(sug.get('expected_effect', ''))}</p>"
            f"{evidence}"
            "</section>")
    return f"<div class='rec-grid'>{''.join(cards)}</div>"


def _review_evidence(scan: dict) -> str:
    reviews = scan.get("reviews", [])
    analyses = scan.get("analyses", {})
    customer_reviews = [
        review for review in reviews
        if review.get("record_type") != "market_signal"
    ]
    market_signals = [
        review for review in reviews
        if review.get("record_type") == "market_signal"
    ]
    parts = []
    parts.append(_review_details(
        "Показать все клиентские отзывы",
        customer_reviews,
        analyses,
        opened=False,
    ))
    parts.append(_review_details(
        "Показать внешние market signals",
        market_signals,
        analyses,
        opened=False,
    ))
    return "".join(parts)


def _review_details(title: str, reviews: list, analyses: dict, opened: bool = False) -> str:
    if not reviews:
        return f"<section class='notice'>Нет данных: {_esc(title.lower())}.</section>"
    ordered = sorted(
        reviews,
        key=lambda item: (item.get("published_at") or item.get("date") or ""),
        reverse=True,
    )
    cards = "".join(
        _review_card(review, analyses.get(review.get("review_id"), {}))
        for review in ordered
    )
    open_attr = " open" if opened else ""
    return (
        f"<details{open_attr}><summary>{_esc(title)} ({len(reviews)})</summary>"
        f"<div class='review-list'>{cards}</div></details>"
    )


def _review_card(review: dict, analysis: dict) -> str:
    title = review.get("title") or review.get("source_name") or review.get("review_id", "")
    date = review.get("published_at") or review.get("date") or ""
    rating = review.get("rating")
    rating_text = f" · рейтинг {rating}" if rating is not None else ""
    sentiment = analysis.get("sentiment", "")
    topics = analysis.get("topics", [])
    text = (
        review.get("full_text")
        or review.get("text")
        or review.get("comments")
        or ""
    )
    pros_cons = ""
    if review.get("pros"):
        pros_cons += f"<p class='review-text'><b>Достоинства:</b> {_esc(review.get('pros'))}</p>"
    if review.get("cons"):
        pros_cons += f"<p class='review-text'><b>Недостатки:</b> {_esc(review.get('cons'))}</p>"
    chips = "".join(f"<span class='chip'>{_esc(topic)}</span>" for topic in topics[:10])
    if sentiment:
        chips = f"<span class='chip'>{_esc(sentiment)}</span>" + chips
    return (
        "<article class='review-card'>"
        f"<h4>{_esc(title)}</h4>"
        f"<div class='review-meta'>{_esc(review.get('source_name', ''))} · {_esc(date)}"
        f"{_esc(rating_text)} · {_link(review.get('url', ''))}</div>"
        f"<p class='review-text'>{_esc(text)}</p>"
        f"{pros_cons}"
        f"<div class='chips'>{chips}</div>"
        "</article>"
    )


def _sentiment_table(counts: dict) -> str:
    labels = ["Очень негативный", "Негативный", "Нейтральный", "Позитивный", "Очень позитивный"]
    total = sum(counts.values()) or 1
    rows = "".join(
        f"<tr><td>{_esc(label)}</td><td>{counts.get(label, 0)}</td><td>{round(counts.get(label, 0) / total * 100, 1)}%</td></tr>"
        for label in labels)
    return f"<table><thead><tr><th>Sentiment</th><th>Отзывы</th><th>Доля</th></tr></thead><tbody>{rows}</tbody></table>"


def _rank_table(items: list, label: str) -> str:
    if not items:
        return "<section class='notice'>Нет данных.</section>"
    rows = "".join(
        f"<tr><td>{idx}</td><td>{_esc(item.get('item', ''))}</td><td>{item.get('count', 0)}</td><td>{_esc(item.get('example', {}).get('quote', ''))}<br><span class='muted'>{_esc(item.get('example', {}).get('source', ''))}</span></td></tr>"
        for idx, item in enumerate(items[:15], start=1))
    return f"<table><thead><tr><th>#</th><th>{_esc(label)}</th><th>Кол-во</th><th>Подтверждение</th></tr></thead><tbody>{rows}</tbody></table>"


def _topic_heatmap(metrics: dict) -> str:
    if not metrics:
        return "<section class='notice'>Нет данных.</section>"
    rows = "".join(
        f"<tr><td>{_esc(topic)}</td><td>{m.get('reviews_count', 0)}</td><td>{m.get('average_rating', '')}</td><td>{round(m.get('negative_share', 0)*100, 1)}%</td><td>{round(m.get('positive_share', 0)*100, 1)}%</td><td>{m.get('criticality_index', 0)}</td><td>{m.get('delta', 0)}</td></tr>"
        for topic, m in sorted(metrics.items(), key=lambda x: (-x[1].get("criticality_index", 0), x[0])))
    return "<table><thead><tr><th>Тема</th><th>Отзывы</th><th>Средний рейтинг</th><th>Негатив</th><th>Позитив</th><th>Индекс критичности</th><th>Δ</th></tr></thead><tbody>" + rows + "</tbody></table>"


def _problems(insights: dict) -> str:
    groups = [
        ("Повторяющиеся", insights.get("repeated_problems", [])),
        ("Новые", insights.get("new_problems", [])),
        ("Исчезнувшие", insights.get("resolved_problems", [])),
    ]
    rows = []
    for name, items in groups:
        for item in items[:12]:
            rows.append(f"<tr><td>{_esc(name)}</td><td>{_esc(item.get('topic', ''))}</td><td>{item.get('reviews_count', item.get('previous_count', ''))}</td><td>{item.get('criticality_index', '')}</td><td>{item.get('delta', '')}</td></tr>")
    if not rows:
        return "<section class='notice'>Проблемы не выявлены или данных недостаточно.</section>"
    return "<table><thead><tr><th>Тип</th><th>Тема</th><th>Отзывы</th><th>Критичность</th><th>Δ</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _source_table(stats: list) -> str:
    rows = "".join(
        f"<tr><td>{_esc(s.get('source_name', ''))}</td><td>{_esc(s.get('review_parser', ''))}</td><td>{_esc(s.get('policy', ''))}</td><td>{_esc(s.get('status', ''))}</td><td>{s.get('fetched_count', 0)}</td><td>{s.get('parsed_count', 0)}</td><td>{_esc(s.get('message', ''))}</td></tr>"
        for s in stats)
    return "<table><thead><tr><th>Источник</th><th>Parser</th><th>Policy</th><th>Status</th><th>Fetched</th><th>Parsed</th><th>Message</th></tr></thead><tbody>" + (rows or "<tr><td colspan='7'>Нет данных</td></tr>") + "</tbody></table>"


def _empty_note(scan: dict) -> str:
    if scan.get("reviews"):
        return ""
    return "<section class='notice warn'><b>Нет данных для анализа</b><br>Источники могли быть заблокированы robots.txt, требовать JS/login или не содержать отзывов за 2026 год.</section>"


def _avg_sentiment_index(analyses: dict):
    values = [a.get("sentiment_index") for a in analyses.values() if a.get("sentiment_index") is not None]
    return round(sum(values) / len(values), 1) if values else "—"


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _link(url: str) -> str:
    if not url:
        return ""
    safe = _esc(url)
    return f"<a href='{safe}' target='_blank' rel='noopener'>{safe}</a>"
