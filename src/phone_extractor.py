
"""
b2b-domain-sniper
File: src/phone_extractor.py

Business Phone Intelligence Engine.

Features:
- Phone number extraction from HTML and text
- tel: link extraction
- Basic international number support
- Number normalization
- Duplicate removal
- Source URL and source type reporting

Note:
This module extracts publicly displayed phone numbers.
It does not verify that a number is active or belongs
to the business.
"""

from __future__ import annotations

import re

from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.parse import unquote


# Matches international and common national phone formats.
PHONE_PATTERN = re.compile(
    r"""
    (?<![\w])
    (?:
        \+\s*\d{1,3}[\s().-]*
    )?
    (?:
        \(?\d{2,4}\)?[\s.-]*
    )
    \d{2,4}
    (?:[\s.-]*\d{2,4}){1,3}
    (?:\s*(?:ext\.?|extension|x)\s*\d{1,6})?
    (?![\w])
    """,
    re.IGNORECASE | re.VERBOSE,
)


TEL_PATTERN = re.compile(
    r"^\s*tel:\s*(.+?)\s*$",
    re.IGNORECASE,
)


class PhoneHTMLParser(HTMLParser):
    """Collect visible text and telephone links from HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)

        self.text_parts: list[str] = []
        self.phone_links: list[str] = []

        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attributes = dict(attrs)

        if tag in {
            "script",
            "style",
            "noscript",
            "svg",
            "template",
        }:
            self._ignored_depth += 1
            return

        if self._ignored_depth:
            return

        href = attributes.get("href", "")

        if href:
            match = TEL_PATTERN.match(href)

            if match:
                self.phone_links.append(
                    unquote(match.group(1).split("?")[0])
                )

        # Some websites store phone numbers in data attributes.
        for key in (
            "data-phone",
            "data-telephone",
            "data-tel",
        ):
            value = attributes.get(key)

            if value:
                self.phone_links.append(str(value))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag in {
            "script",
            "style",
            "noscript",
            "svg",
            "template",
        }:
            if self._ignored_depth > 0:
                self._ignored_depth -= 1

            return

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return

        if data and data.strip():
            self.text_parts.append(data.strip())


def normalize_phone(phone: str) -> str:
    """Normalize a phone number while preserving its country prefix."""

    if not isinstance(phone, str):
        return ""

    phone = phone.strip()

    phone = re.sub(
        r"\s*(?:ext\.?|extension|x)\s*",
        " ext ",
        phone,
        flags=re.IGNORECASE,
    )

    phone = re.sub(r"\s+", " ", phone)

    return phone.strip(" .,;:|")


def _phone_digits(phone: str) -> str:
    """Return digits only, excluding extension digits."""

    base = re.split(
        r"\bext\b",
        phone,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    return re.sub(r"\D", "", base)


def _is_valid_phone_candidate(phone: str) -> bool:
    """Apply basic length and formatting checks."""

    if not phone:
        return False

    digits = _phone_digits(phone)

    # International phone numbers generally contain 7-15 digits.
    if not 7 <= len(digits) <= 15:
        return False

    # Reject repeated-digit placeholders.
    if len(set(digits)) == 1:
        return False

    # Reject likely years or short numeric fragments.
    if digits in {
        "1234567890",
        "0123456789",
        "9876543210",
    }:
        return False

    return True


def _extract_candidates(text: str) -> list[str]:
    """Extract phone-like strings from text."""

    if not isinstance(text, str) or not text:
        return []

    return PHONE_PATTERN.findall(text)


def extract_phones(
    html: str = "",
    text: str = "",
    max_results: int = 100,
) -> list[str]:
    """
    Extract unique phone numbers from HTML and plain text.

    Returns:
        List of normalized phone number strings.
    """

    parser = PhoneHTMLParser()

    if html:
        try:
            parser.feed(html)
            parser.close()
        except Exception:
            pass

    searchable_text = " ".join(
        [
            text or "",
            " ".join(parser.text_parts),
        ]
    )

    candidates = list(parser.phone_links)
    candidates.extend(
        _extract_candidates(searchable_text)
    )

    results: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        phone = normalize_phone(str(candidate))

        if not _is_valid_phone_candidate(phone):
            continue

        key = re.sub(r"\D", "", phone)

        if key in seen:
            continue

        seen.add(key)
        results.append(phone)

        if len(results) >= max_results:
            break

    return results


def extract_phone_details(
    html: str = "",
    text: str = "",
) -> list[dict[str, str]]:
    """Return phone numbers with basic source classification."""

    parser = PhoneHTMLParser()

    if html:
        try:
            parser.feed(html)
            parser.close()
        except Exception:
            pass

    results: list[dict[str, str]] = []
    seen: set[str] = set()

    candidates = [
        (number, "tel_link")
        for number in parser.phone_links
    ]

    searchable_text = " ".join(
        [text or "", " ".join(parser.text_parts)]
    )

    candidates.extend(
        (number, "website_content")
        for number in _extract_candidates(searchable_text)
    )

    for candidate, source_type in candidates:
        phone = normalize_phone(str(candidate))

        if not _is_valid_phone_candidate(phone):
            continue

        key = re.sub(r"\D", "", phone)

        if key in seen:
            continue

        seen.add(key)

        results.append({
            "phone": phone,
            "normalized_digits": _phone_digits(phone),
            "source_type": source_type,
        })

    return results


def extract_from_pages(
    pages: Iterable[dict[str, Any]],
    max_results: int = 200,
) -> list[dict[str, str]]:
    """
    Extract and deduplicate phone numbers across crawler pages.

    Expected page structure:
        {
            "url": "...",
            "html": "...",
            "text": "..."
        }
    """

    collected: dict[str, dict[str, str]] = {}

    for page in pages:
        if not isinstance(page, dict):
            continue

        html = str(page.get("html") or "")
        text = str(page.get("text") or "")
        url = str(page.get("url") or "")

        details = extract_phone_details(
            html=html,
            text=text,
        )

        for item in details:
            key = item["normalized_digits"]

            if key not in collected:
                collected[key] = {
                    "phone": item["phone"],
                    "normalized_digits": key,
                    "source_url": url,
                    "source_type": item["source_type"],
                }

            if len(collected) >= max_results:
                return list(collected.values())

    return list(collected.values())
