
"""
b2b-domain-sniper
File: src/intent_scorer.py

Business Intent Intelligence Engine.

Features:
- Multi-signal intent scoring
- Email intelligence
- MX configuration analysis
- Hiring signal analysis
- Technology intelligence
- Lead quality classification
- Configurable scoring weights
- Explainable score breakdown
"""

from __future__ import annotations

from typing import Any


DEFAULT_WEIGHTS = {
    "email": 15,
    "mx": 15,
    "hiring": 30,
    "technology": 20,
    "website": 10,
    "business_growth": 10,
}


def clamp_score(value: float) -> float:
    """Keep score between 0 and 100."""

    return round(max(0.0, min(100.0, value)), 2)


def normalize_weights(
    weights: dict[str, float] | None = None,
) -> dict[str, float]:
    """Normalize scoring weights to a 100-point scale."""

    source = weights or DEFAULT_WEIGHTS

    cleaned = {}

    for key, value in source.items():
        try:
            number = float(value)

            if number >= 0:
                cleaned[key] = number

        except (TypeError, ValueError):
            continue

    total = sum(cleaned.values())

    if total <= 0:
        raise ValueError("At least one positive weight is required")

    return {
        key: value / total * 100
        for key, value in cleaned.items()
    }


def score_email(data: dict[str, Any]) -> float:
    """Score available business email intelligence."""

    emails = data.get("emails", [])

    if isinstance(emails, dict):
        emails = emails.get("results", [])

    if not isinstance(emails, list):
        return 0.0

    valid_emails = [
        item for item in emails
        if isinstance(item, str) and "@" in item
    ]

    if not valid_emails:
        return 0.0

    return min(100.0, 40.0 + len(valid_emails) * 10.0)


def score_mx(data: dict[str, Any]) -> float:
    """Score domain mail configuration."""

    mx = data.get("mx_validation", data.get("mx", {}))

    if not isinstance(mx, dict):
        return 0.0

    status = mx.get("status")

    if status == "valid_mx":
        return 100.0

    if status == "implicit_mx_fallback":
        return 60.0

    if status == "no_mail_routing_records":
        return 0.0

    return 0.0


def score_hiring(data: dict[str, Any]) -> float:
    """Score publicly visible recruitment signals."""

    hiring = data.get("hiring", {})

    if not isinstance(hiring, dict):
        return 0.0

    raw_score = hiring.get("hiring_score", 0)

    try:
        return clamp_score(float(raw_score))
    except (TypeError, ValueError):
        return 0.0


def score_technology(data: dict[str, Any]) -> float:
    """Score detected website technology signals."""

    technology = data.get("technology", {})

    if not isinstance(technology, dict):
        return 0.0

    count = technology.get(
        "technology_count",
        len(technology.get("technologies", [])),
    )

    try:
        count = max(0, int(count))
    except (TypeError, ValueError):
        return 0.0

    return min(100.0, count * 15.0)


def score_website(data: dict[str, Any]) -> float:
    """Score website availability and crawl coverage."""

    website = data.get("website", {})

    if not isinstance(website, dict):
        return 0.0

    score = 0.0

    if website.get("reachable") is True:
        score += 50.0

    pages = website.get("pages_analyzed", 0)

    try:
        pages = max(0, int(pages))
    except (TypeError, ValueError):
        pages = 0

    score += min(50.0, pages * 10.0)

    return clamp_score(score)


def score_business_growth(data: dict[str, Any]) -> float:
    """Score explicitly supplied business growth indicators."""

    growth = data.get("business_growth", {})

    if not isinstance(growth, dict):
        return 0.0

    indicators = growth.get("indicators", [])

    if not isinstance(indicators, list):
        return 0.0

    return min(100.0, len(indicators) * 20.0)


def classify_intent(score: float) -> str:
    """Classify overall business intent."""

    if score >= 75:
        return "high"

    if score >= 45:
        return "medium"

    return "low"


def classify_lead_quality(score: float) -> str:
    """Classify lead quality."""

    if score >= 80:
        return "excellent"

    if score >= 65:
        return "good"

    if score >= 40:
        return "moderate"

    return "weak"


def calculate_intent(
    data: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Calculate an explainable business intent score.

    Missing signals contribute zero rather than being
    treated as confirmed negative evidence.
    """

    if not isinstance(data, dict):
        raise TypeError("Input data must be a dictionary")

    normalized_weights = normalize_weights(weights)

    scorers = {
        "email": score_email,
        "mx": score_mx,
        "hiring": score_hiring,
        "technology": score_technology,
        "website": score_website,
        "business_growth": score_business_growth,
    }

    breakdown = {}
    available_signals = []

    weighted_total = 0.0
    available_weight = 0.0

    for name, weight in normalized_weights.items():

        scorer = scorers.get(name)

        if scorer is None:
            continue

        component_score = clamp_score(scorer(data))

        # Only score signals actually supplied by the caller.
        signal_keys = {
            "email": ("emails",),
            "mx": ("mx", "mx_validation"),
            "hiring": ("hiring",),
            "technology": ("technology",),
            "website": ("website",),
            "business_growth": ("business_growth",),
        }

        is_available = any(
            key in data and data[key] is not None
            for key in signal_keys[name]
        )

        breakdown[name] = {
            "score": component_score,
            "weight": round(weight, 2),
            "weighted_score": 0.0,
            "available": is_available,
        }

        if is_available:
            available_signals.append(name)
            weighted_total += component_score * weight
            available_weight += weight

    # Avoid penalizing missing signals.
    final_score = (
        weighted_total / available_weight
        if available_weight > 0
        else 0.0
    )

    for name, item in breakdown.items():
        if item["available"] and available_weight > 0:
            item["weighted_score"] = round(
                item["score"]
                * item["weight"]
                / available_weight,
                2,
            )

    final_score = clamp_score(final_score)

    return {
        "intent_score": final_score,
        "intent_level": classify_intent(final_score),
        "lead_quality": classify_lead_quality(final_score),
        "score_breakdown": breakdown,
        "signals_analyzed": len(available_signals),
        "available_signals": available_signals,
        "scoring_version": "1.0",
    }


def get_intent_summary(
    result: dict[str, Any],
) -> str:
    """Generate a short human-readable intent summary."""

    level = result.get("intent_level", "unknown")
    score = result.get("intent_score", 0)

    return (
        f"Business intent is {level.upper()} "
        f"with a score of {score}/100."
    )
