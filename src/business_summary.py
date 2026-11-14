
"""
b2b-domain-sniper
File: src/business_summary.py

Business Summary Generation Engine.

Features:
- Homepage meta description extraction
- Open Graph description support
- Multi-page content analysis
- Relevant sentence selection
- Duplicate sentence removal
- Summary length control
- Source URL reporting

Note:
This module creates an extractive summary from website content.
It does not generate facts that are not present on the website.
"""

from __future__ import annotations

import re

from typing import Any, Iterable


MAX_DEFAULT_LENGTH = 500


IGNORED_SENTENCE_PATTERNS = [
    r"^cookie policy",
    r"^privacy policy",
    r"^terms of service",
    r"^all rights reserved",
    r"^sign up",
    r"^log in",
    r"^login",
    r"^subscribe",
    r"^read more",
    r"^learn more$",
    r"^contact us$",
    r"^home$",
]


SUMMARY_KEYWORDS = {
    "company",
    "business",
    "provides",
    "provider",
    "offers",
    "services",
    "products",
    "platform",
    "solutions",
    "customers",
    "clients",
    "industry",
    "software",
    "technology",
    "manufacturing",
    "consulting",
    "support",
    "develops",
    "specializes",
    "specialises",
    "help",
    "helping",
    "organization",
    "organisation",
}


def _normalize_text(value: Any) -> str:
    """Normalize whitespace and invisible characters."""

    if not isinstance(value, str):
        return ""

    value = value.replace("\x00", "")
    value = value.replace("\u200b", "")
    value = value.replace("\ufeff", "")

    value = re.sub(r"[\t\r\n]+", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def _clean_description(value: str) -> str:
    """Clean a description without changing its meaning."""

    value = _normalize_text(value)

    value = value.strip(" \t\n\r\"'")

    value = re.sub(
        r"\s*\|\s*(?:home|homepage)$",
        "",
        value,
        flags=re.IGNORECASE,
    )

    return value.strip()


def _get_page_description(
    page: dict[str, Any],
) -> str:
    """Get description from crawler fields or metadata."""

    description = page.get("description")

    if description:
        return _clean_description(str(description))

    metadata = page.get("metadata")

    if not isinstance(metadata, dict):
        metadata = {}

    for key in (
        "description",
        "og:description",
        "twitter:description",
    ):
        value = metadata.get(key)

        if value:
            return _clean_description(str(value))

    return ""


def _is_ignored_sentence(sentence: str) -> bool:
    """Reject common navigation and policy fragments."""

    normalized = sentence.strip().lower()

    for pattern in IGNORED_SENTENCE_PATTERNS:
        if re.search(pattern, normalized):
            return True

    return False


def _split_sentences(text: str) -> list[str]:
    """Split text into sentence-like segments."""

    text = _normalize_text(text)

    if not text:
        return []

    # Keep common abbreviations from causing excessive splits.
    text = re.sub(
        r"\b(e\.g|i\.e|mr|mrs|dr|inc|ltd|co)\.",
        lambda match: match.group(0).replace(".", "<DOT>"),
        text,
        flags=re.IGNORECASE,
    )

    parts = re.split(
        r"(?<=[.!?])\s+|(?<=;)\s+",
        text,
    )

    sentences = []

    for part in parts:
        sentence = part.replace("<DOT>", ".").strip()

        if not sentence:
            continue

        if len(sentence) < 35:
            continue

        if _is_ignored_sentence(sentence):
            continue

        sentences.append(sentence)

    return sentences


def _sentence_score(sentence: str) -> int:
    """Score sentences based on business-related language."""

    words = re.findall(
        r"\b[a-zA-Z][a-zA-Z'-]*\b",
        sentence.lower(),
    )

    if not words:
        return 0

    score = 0

    for word in words:
        if word in SUMMARY_KEYWORDS:
            score += 2

    if len(words) >= 8:
        score += 1

    if len(words) >= 15:
        score += 1

    if len(words) > 60:
        score -= 2

    return score


def _select_sentences(
    text: str,
    max_length: int,
    max_sentences: int = 3,
) -> str:
    """Select relevant sentences while preserving original order."""

    sentences = _split_sentences(text)

    if not sentences:
        return ""

    ranked = sorted(
        enumerate(sentences),
        key=lambda item: (
            _sentence_score(item[1]),
            -item[0],
        ),
        reverse=True,
    )

    selected_indexes: set[int] = set()

    for index, sentence in ranked:
        if len(selected_indexes) >= max_sentences:
            break

        if _sentence_score(sentence) <= 0:
            continue

        selected_indexes.add(index)

    # If no business-related sentence matched, use the first
    # meaningful sentence instead of inventing a summary.
    if not selected_indexes:
        selected_indexes.add(0)

    selected = [
        sentence
        for index, sentence in enumerate(sentences)
        if index in selected_indexes
    ]

    result = " ".join(selected).strip()

    if len(result) > max_length:
        result = result[:max_length].rsplit(" ", 1)[0].rstrip()

        if result and result[-1] not in ".!?":
            result += "..."

    return result


def generate_business_summary(
    pages: Iterable[dict[str, Any]],
    existing_description: str | None = None,
    max_length: int = MAX_DEFAULT_LENGTH,
) -> str | None:
    """
    Generate a business description from website pages.

    Priority:
        1. Existing homepage description
        2. Homepage metadata description
        3. Relevant homepage text
        4. Relevant text from other crawled pages

    Returns:
        A clean description string, or None if no useful
        information is available.
    """

    if max_length < 50:
        raise ValueError(
            "max_length must be at least 50 characters."
        )

    page_list = [
        page
        for page in pages
        if isinstance(page, dict)
    ]

    if existing_description:
        description = _clean_description(
            existing_description
        )

        if description:
            if len(description) > max_length:
                description = (
                    description[:max_length]
                    .rsplit(" ", 1)[0]
                    .rstrip()
                )

                if description and description[-1] not in ".!?":
                    description += "..."

            return description

    if not page_list:
        return None

    # Prefer the first page, which is normally the homepage.
    homepage = page_list[0]

    homepage_description = _get_page_description(
        homepage
    )

    if homepage_description:
        if len(homepage_description) > max_length:
            homepage_description = (
                homepage_description[:max_length]
                .rsplit(" ", 1)[0]
                .rstrip()
            )

            if homepage_description and homepage_description[-1] not in ".!?":
                homepage_description += "..."

        return homepage_description

    homepage_text = _normalize_text(
        homepage.get("text") or ""
    )

    summary = _select_sentences(
        homepage_text,
        max_length=max_length,
    )

    if summary:
        return summary

    # Use other pages only when homepage content is insufficient.
    for page in page_list[1:]:
        text = _normalize_text(
            page.get("text") or ""
        )

        summary = _select_sentences(
            text,
            max_length=max_length,
        )

        if summary:
            return summary

    return None


def build_business_summary(
    pages: Iterable[dict[str, Any]],
    existing_description: str | None = None,
    max_length: int = MAX_DEFAULT_LENGTH,
) -> dict[str, Any]:
    """
    Build a structured business summary result.

    Returns:
        {
            "summary": "...",
            "source_url": "...",
            "summary_status": "generated"
        }
    """

    page_list = [
        page
        for page in pages
        if isinstance(page, dict)
    ]

    summary = generate_business_summary(
        pages=page_list,
        existing_description=existing_description,
        max_length=max_length,
    )

    source_url = None

    if summary and page_list:
        source_url = str(
            page_list[0].get("url") or ""
        ) or None

    return {
        "summary": summary,
        "source_url": source_url,
        "summary_status": (
            "generated"
            if summary
            else "insufficient_content"
        ),
        "method": "extractive_website_summary",
    }
