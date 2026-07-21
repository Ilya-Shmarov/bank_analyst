# -*- coding: utf-8 -*-
"""Known premium benefit names used only to classify extracted source text.

This catalog is not a data source. It must not create a benefit by itself or
fill a missing field. The parser may use it only after a source has already
provided a text fragment for a concrete bank tier.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BenefitPattern:
    benefit_id: str
    title: str
    markers: tuple[str, ...]
    description: str = ""


BENEFIT_PATTERNS = (
    BenefitPattern("sber_prime", "СберПрайм", ("сберпрайм", "подписка сберпрайм")),
    BenefitPattern("okko", "Okko", ("okko",)),
    BenefitPattern("samokat", "Самокат", ("самокат",)),
    BenefitPattern("pets", "Питомцы", ("питомцы",)),
    BenefitPattern("health", "Здоровье", ("здоровье",)),
    BenefitPattern("sport_beauty", "Спорт и красота", ("спорт и красота",)),
    BenefitPattern("entertainment", "Развлечения", ("развлечения",)),
    BenefitPattern("sber_mobile", "Сбер Мобайл", ("сбер мобайл", "сбермобайл")),
    BenefitPattern("sber_pravo", "СберПраво", ("сберправо", "сбер право")),
    BenefitPattern("pb_service", "Консьерж Pb Service", ("pb service",)),

    BenefitPattern("legal_accounting", "Консультации с юристом и бухгалтером",
                   ("консультации с юристом", "бухгалтером")),
    BenefitPattern("alfa_mobile", "Альфа-Мобайл", ("альфа-мобайл", "альфа‑мобайл")),
    BenefitPattern("smart_reading", "Саммари от Smart Reading", ("smart reading",)),
    BenefitPattern("rbc", "РБК", ("рбк",), "Подписка"),
    BenefitPattern("only_assist", "Only Assist", ("only assist",), "Консьерж-сервис на платформе Konsierge"),
    BenefitPattern("prime", "PRIME", ("prime", "консьерж-сервис prime"), "Консьерж-сервис"),
    BenefitPattern("alfa_lounge", "Alfa Only Лаундж",
                   ("alfa only lounge", "alfa only лаундж")),
    BenefitPattern("aclub_lounge", "А-Клуб Лаундж",
                   ("а-клуб lounge", "а-клуб лаундж")),
    BenefitPattern("simple_prive", "Закрытый винный клуб SimplePrivé",
                   ("simpleprivé", "simpleprive", "винный клуб")),
    BenefitPattern("medical_concierge", "Медицинский консьерж",
                   ("медицинский консьерж",)),
)

_INDEX = {pattern.benefit_id: pattern for pattern in BENEFIT_PATTERNS}


def classify_benefit(text: str) -> Optional[BenefitPattern]:
    """Return a known benefit pattern when a source fragment names it."""
    low = _normalize(text)
    for pattern in BENEFIT_PATTERNS:
        if any(_normalize(marker) in low for marker in pattern.markers):
            return pattern
    return None


def benefit_id_for_title(title: str) -> str:
    """Return a stable id for a title, using the catalog when possible."""
    pattern = classify_benefit(title)
    if pattern:
        return pattern.benefit_id
    low = _normalize(title)
    return re.sub(r"[^a-zа-я0-9]+", "_", low).strip("_")


def canonical_title(title: str) -> str:
    pattern = classify_benefit(title)
    return pattern.title if pattern else title


def default_description(benefit_id: str) -> str:
    pattern = _INDEX.get(benefit_id)
    return pattern.description if pattern else ""


def _normalize(text: str) -> str:
    return str(text).lower().replace("ё", "е").replace("‑", "-")
