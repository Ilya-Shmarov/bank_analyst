# -*- coding: utf-8 -*-
"""Data models for Customer Feedback Intelligence."""

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class FeedbackReview:
    review_id: str
    source_id: str
    source_name: str
    url: str
    date: str
    published_at: str
    scanned_at: str
    author: str
    title: str
    text: str
    full_text: str
    pros: str
    cons: str
    comments: str
    rating: Optional[float]
    likes_count: Optional[int]
    comments_count: Optional[int]
    product_id: str
    record_type: str
    data_source: str
    source_url: str
    office: str
    language: str
    collected_at: str
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FeedbackAnalysis:
    review_id: str
    sentiment: str
    sentiment_score: float
    sentiment_index: float
    emotions: list
    topics: list
    advantages: list
    disadvantages: list
    complaint_phrases: list
    wish_phrases: list
    emotion_score: float
    is_complaint: bool
    is_wish: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FeedbackSuggestion:
    suggestion_id: str
    title: str
    basis: str
    affected_categories: list
    problem_description: str
    recommended_change: str
    expected_effect: str
    quotes_with_sources: list
    supporting_review_ids: list
    support_count: int
    source_count: int
    mass_score: float
    negative_score: float
    recency_score: float
    repeatability_score: float
    source_diversity_score: float
    priority: str
    priority_score: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FeedbackInsight:
    advantages: list
    disadvantages: list
    wishes: list
    repeated_problems: list
    new_problems: list
    resolved_problems: list
    topic_metrics: dict

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FeedbackScan:
    date: str
    reviews: list
    analyses: dict
    suggestions: list
    trends: dict
    meta: dict

    def to_dict(self) -> dict:
        return asdict(self)
