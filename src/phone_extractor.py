"""Extract likely public business telephone numbers from website pages.

This module applies conservative formatting/length checks to reduce false
positives. It does not confirm that a number is assigned, active, or owned by
the website operator. National numbers without a country context remain
inherently ambiguous.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.parse import unquote

PHONE_PATTERN = re.compile(
    r"(?<![\w])"
    r"(?:\+\s*\d{1,3}[\s().-]*)?"
    r"(?:\(\s*\d{2,4}\s*\)|\d{2,4})"
    r"(?:[\s.-]+\d{2,4}){2,4}"
    r"(?:\s*(?:ext\.?|extension|x)\s*\d{1,6})?"
    r"(?![\w])",
    re.IGNORECASE,
)

TEL_PATTERN = re.compile(r"^\s*tel:\s*(.+?)\s*$", re.I)
EXTENSION_PATTERN = re.compile(
    r"\b(?:ext\.?|extension|x)\s*\d+\s*$",
    re.IGNORECASE,
)


class PhoneHTMLParser(HTMLParser):
    """Collect visible text and telephone links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.phone_links: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attributes = dict(attrs)

        if tag in {"script", "style", "noscript", "svg", "template"}:
            self._ignored_depth += 1
            return

        if self._ignored_depth:
            return

        href = attributes.get("href") or ""
        match = TEL_PATTERN.match(href)

        if match:
            self.phone_links.append(
                unquote(match.group(1).split("?", 1)[0])
            )

        for key in ("data-phone", "data-telephone", "data-tel"):
            value = attributes.get(key)

            if value:
                self.phone_links.append(str(value))

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {
            "script", "style", "noscript", "svg", "template"
        }:
            if self._ignored_depth:
                self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data and data.strip():
            self.text_parts.append(data.strip())


def normalize_phone(phone: str) -> str:
    if not isinstance(phone, str):
        return ""

    value = phone.strip()
    value = re.sub(
        r"\s*(?:ext\.?|extension|x)\s*",
        " ext ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\s+", " ", value)

    return value.strip(" .,;:|")


def _phone_digits(phone: str) -> str:
    base = EXTENSION_PATTERN.sub("", phone)

    return re.sub(r"\D", "", base)


def _is_valid_phone_candidate(
    phone: str,
    *,
    from_tel_link: bool = False,
) -> bool:
    if not phone:
        return False

    digits = _phone_digits(phone)
    minimum = 7 if from_tel_link else 10

    if not minimum <= len(digits) <= 15:
        return False

    if len(set(digits)) == 1:
        return False

    if digits in {
        "1234567890",
        "0123456789",
        "9876543210",
    }:
        return False

    # Reject bare numeric fragments in ordinary page text.
    if not from_tel_link and not any(
        char in phone for char in "+().- "
    ):
        return False

    return True


def _extract_candidates(text: str) -> list[str]:
    """Extract candidates only when formatting or nearby wording supports them."""
    if not isinstance(text, str) or not text:
        return []

    candidates: list[str] = []

    context_pattern = re.compile(
        r"\b(?:phone|telephone|tel|call|fax|mobile|cell|contact)\b",
        re.IGNORECASE,
    )

    for match in PHONE_PATTERN.finditer(text):
        candidate = match.group(0).strip()

        # Explicit international prefix is a stronger signal.
        if candidate.startswith("+"):
            candidates.append(candidate)
            continue

        left = max(0, match.start() - 18)
        preceding_context = text[left:match.start()]

        # A later label must not validate an earlier unrelated number.
        preceding_context = re.split(
            r"[.!?;\n]",
            preceding_context,
        )[-1]

        if context_pattern.search(preceding_context):
            candidates.append(candidate)

    return candidates


def extract_phones(
    html: str = "",
    text: str = "",
    max_results: int = 100,
) -> list[str]:
    if max_results <= 0:
        return []

    parser = PhoneHTMLParser()

    if isinstance(html, str) and html:
        try:
            parser.feed(html)
            parser.close()
        except Exception:
            pass

    searchable = " ".join(
        [
            text if isinstance(text, str) else "",
            " ".join(parser.text_parts),
        ]
    )

    candidates = [
        (value, True)
        for value in parser.phone_links
    ]

    candidates.extend(
        (value, False)
        for value in _extract_candidates(searchable)
    )

    results: list[str] = []
    seen: set[str] = set()

    for candidate, from_tel_link in candidates:
        phone = normalize_phone(str(candidate))

        if not _is_valid_phone_candidate(
            phone,
            from_tel_link=from_tel_link,
        ):
            continue

        key = _phone_digits(phone)

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
    parser = PhoneHTMLParser()

    if isinstance(html, str) and html:
        try:
            parser.feed(html)
            parser.close()
        except Exception:
            pass

    searchable = " ".join(
        [
            text if isinstance(text, str) else "",
            " ".join(parser.text_parts),
        ]
    )

    candidates = [
        (value, "tel_link", True)
        for value in parser.phone_links
    ]

    candidates.extend(
        (value, "website_content", False)
        for value in _extract_candidates(searchable)
    )

    results: list[dict[str, str]] = []
    seen: set[str] = set()

    for candidate, source_type, from_tel_link in candidates:
        phone = normalize_phone(str(candidate))

        if not _is_valid_phone_candidate(
            phone,
            from_tel_link=from_tel_link,
        ):
            continue

        digits = _phone_digits(phone)

        if digits in seen:
            continue

        seen.add(digits)

        results.append(
            {
                "phone": phone,
                "normalized_digits": digits,
                "source_type": source_type,
            }
        )

    return results


def extract_from_pages(
    pages: Iterable[dict[str, Any]],
    max_results: int = 200,
) -> list[dict[str, str]]:
    if max_results <= 0:
        return []

    collected: dict[str, dict[str, str]] = {}

    for page in pages:
        if not isinstance(page, dict):
            continue

        details = extract_phone_details(
            html=str(page.get("html") or ""),
            text=str(page.get("text") or ""),
        )

        for item in details:
            key = item["normalized_digits"]

            collected.setdefault(
                key,
                {
                    **item,
                    "source_url": str(page.get("url") or ""),
                },
            )

            if len(collected) >= max_results:
                return list(collected.values())

    return list(collected.values())
