
"""
b2b-domain-sniper
File: src/industry_detector.py

Business Industry Detection Engine.

Features:
- Keyword-based industry classification
- Multi-page website analysis
- Weighted keyword matching
- Confidence score
- Matched keyword reporting
- Multiple industry candidates

Note:
Classification is based on public website content.
It is not a verified legal business classification.
"""

from __future__ import annotations

import re

from typing import Any, Iterable


INDUSTRY_KEYWORDS: dict[str, list[str]] = {

    "Software & SaaS": [
        "software",
        "saas",
        "cloud platform",
        "business software",
        "software platform",
        "crm software",
        "enterprise software",
        "api platform",
        "automation software",
        "developer tools",
    ],

    "Information Technology": [
        "information technology",
        "it services",
        "managed it",
        "technical support",
        "it consulting",
        "network infrastructure",
        "cybersecurity",
        "cloud computing",
        "data center",
    ],

    "Marketing & Advertising": [
        "digital marketing",
        "marketing agency",
        "advertising agency",
        "seo services",
        "social media marketing",
        "content marketing",
        "lead generation",
        "brand strategy",
        "marketing automation",
    ],

    "Financial Services": [
        "financial services",
        "financial planning",
        "wealth management",
        "investment management",
        "asset management",
        "financial advisory",
        "capital markets",
        "financial consulting",
    ],

    "Banking": [
        "banking",
        "commercial bank",
        "retail banking",
        "business banking",
        "checking account",
        "savings account",
        "bank loans",
    ],

    "Insurance": [
        "insurance",
        "insurance company",
        "life insurance",
        "health insurance",
        "business insurance",
        "insurance broker",
        "insurance coverage",
    ],

    "Healthcare": [
        "healthcare",
        "medical services",
        "health services",
        "medical clinic",
        "patient care",
        "healthcare provider",
        "hospital",
        "medical center",
    ],

    "Pharmaceuticals & Biotechnology": [
        "pharmaceutical",
        "pharmaceuticals",
        "biotechnology",
        "biotech",
        "drug discovery",
        "clinical research",
        "medical research",
        "life sciences",
    ],

    "Education": [
        "education",
        "educational services",
        "online learning",
        "e-learning",
        "learning platform",
        "school",
        "university",
        "training courses",
        "academic programs",
    ],

    "E-commerce & Retail": [
        "ecommerce",
        "e-commerce",
        "online store",
        "online shopping",
        "retail store",
        "shop products",
        "product catalog",
        "consumer products",
    ],

    "Manufacturing": [
        "manufacturing",
        "manufacturer",
        "industrial production",
        "production facility",
        "factory",
        "industrial equipment",
        "manufactured products",
    ],

    "Construction & Real Estate": [
        "real estate",
        "property management",
        "commercial property",
        "residential property",
        "construction company",
        "building contractor",
        "property development",
        "real estate development",
    ],

    "Logistics & Transportation": [
        "logistics",
        "transportation",
        "supply chain",
        "freight services",
        "shipping services",
        "warehouse management",
        "delivery services",
        "fleet management",
    ],

    "Hospitality & Travel": [
        "hospitality",
        "hotel",
        "resort",
        "travel agency",
        "tourism",
        "vacation rentals",
        "restaurant",
        "accommodation",
    ],

    "Telecommunications": [
        "telecommunications",
        "telecom services",
        "wireless network",
        "mobile network",
        "internet service provider",
        "broadband services",
        "fiber optic network",
    ],

    "Energy & Utilities": [
        "renewable energy",
        "solar energy",
        "wind energy",
        "energy solutions",
        "electric utility",
        "power generation",
        "oil and gas",
        "energy infrastructure",
    ],

    "Professional Services": [
        "consulting services",
        "management consulting",
        "professional services",
        "business consulting",
        "legal services",
        "accounting services",
        "human resources consulting",
    ],

    "Automotive": [
        "automotive",
        "automobile",
        "car dealership",
        "vehicle manufacturing",
        "auto parts",
        "automotive technology",
        "vehicle services",
    ],

    "Food & Beverage": [
        "food production",
        "food manufacturing",
        "beverage company",
        "food products",
        "food distribution",
        "food processing",
        "beverage manufacturing",
    ],

    "Media & Entertainment": [
        "media company",
        "entertainment",
        "video production",
        "film production",
        "music production",
        "digital media",
        "publishing",
        "broadcasting",
    ],
}


# Stronger phrases receive higher weights.
STRONG_PHRASES = {
    "software",
    "saas",
    "healthcare",
    "financial services",
    "insurance",
    "manufacturing",
    "real estate",
    "logistics",
    "telecommunications",
    "pharmaceutical",
    "biotechnology",
    "e-commerce",
    "ecommerce",
}


def _normalize_text(value: str) -> str:
    """Normalize text for keyword matching."""

    value = value.lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[\W_]+", " ", value)

    return re.sub(r"\s+", " ", value).strip()


def _page_search_text(page: dict[str, Any]) -> str:
    """Build searchable text from a crawler page."""

    parts = [
        str(page.get("title") or ""),
        str(page.get("description") or ""),
        str(page.get("text") or ""),
        str(page.get("keywords") or ""),
    ]

    metadata = page.get("metadata")

    if isinstance(metadata, dict):
        parts.extend(
            str(value)
            for value in metadata.values()
            if isinstance(value, (str, int, float))
        )

    return _normalize_text(" ".join(parts))


def detect_industry(
    text: str,
    max_results: int = 5,
) -> dict[str, Any]:
    """
    Detect possible industries from a single text block.

    Returns:
        primary_industry
        confidence
        candidates
        matched_keywords
        detection_status
    """

    searchable = _normalize_text(text or "")

    if not searchable:
        return {
            "primary_industry": None,
            "confidence": 0.0,
            "candidates": [],
            "matched_keywords": [],
            "detection_status": "insufficient_content",
        }

    scores: dict[str, float] = {}
    matches: dict[str, list[str]] = {}

    for industry, keywords in INDUSTRY_KEYWORDS.items():

        score = 0.0
        matched: list[str] = []

        for keyword in keywords:
            normalized_keyword = _normalize_text(keyword)

            if not normalized_keyword:
                continue

            # Match complete phrases, not arbitrary substrings.
            pattern = (
                r"(?<!\w)"
                + re.escape(normalized_keyword)
                + r"(?!\w)"
            )

            occurrences = len(
                re.findall(pattern, searchable)
            )

            if not occurrences:
                continue

            weight = (
                3.0
                if keyword.lower() in STRONG_PHRASES
                else 1.5
            )

            score += min(occurrences, 3) * weight
            matched.append(keyword)

        if score:
            scores[industry] = score
            matches[industry] = matched

    if not scores:
        return {
            "primary_industry": None,
            "confidence": 0.0,
            "candidates": [],
            "matched_keywords": [],
            "detection_status": "not_detected",
        }

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    total_score = sum(scores.values())
    top_score = ranked[0][1]

    # Confidence is a heuristic, not a statistical probability.
    confidence = min(
        0.95,
        round(top_score / max(total_score, 1.0), 2),
    )

    candidates = []

    for industry, score in ranked[:max_results]:
        candidates.append({
            "industry": industry,
            "score": round(score, 2),
            "matched_keywords": matches[industry],
        })

    return {
        "primary_industry": ranked[0][0],
        "confidence": confidence,
        "candidates": candidates,
        "matched_keywords": matches[ranked[0][0]],
        "detection_status": "detected",
        "classification_method": "weighted_keyword_matching",
    }


def detect_industry_from_pages(
    pages: Iterable[dict[str, Any]],
    max_results: int = 5,
) -> dict[str, Any]:
    """
    Detect industry using multiple crawler pages.

    Homepage title and description are included through the
    normal page fields. Repeated content is deduplicated.
    """

    page_texts: list[str] = []
    seen: set[str] = set()
    pages_analyzed = 0

    for page in pages:
        if not isinstance(page, dict):
            continue

        searchable = _page_search_text(page)

        if not searchable:
            continue

        if searchable in seen:
            continue

        seen.add(searchable)
        page_texts.append(searchable)
        pages_analyzed += 1

    combined_text = " ".join(page_texts)

    result = detect_industry(
        combined_text,
        max_results=max_results,
    )

    result["pages_analyzed"] = pages_analyzed

    return result
