
"""
b2b-domain-sniper
File: src/location_extractor.py

Business Location Intelligence Engine.

Features:
- JSON-LD address extraction
- Schema.org PostalAddress support
- Meta location extraction
- Address text extraction
- Multi-page location analysis
- Source URL reporting
- Duplicate removal

Note:
Only publicly available website information is analyzed.
Location values are not independently verified.
"""

from __future__ import annotations

import json
import re

from html.parser import HTMLParser
from typing import Any, Iterable


LOCATION_META_KEYS = {
    "geo.placename",
    "place:location:latitude",
    "place:location:longitude",
    "og:locality",
    "og:region",
    "og:country-name",
    "address",
    "business:contact_data:locality",
    "business:contact_data:region",
    "business:contact_data:country_name",
}


class LocationHTMLParser(HTMLParser):
    """Extract metadata and JSON-LD scripts from HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)

        self.metadata: dict[str, str] = {}
        self.json_ld_blocks: list[str] = []

        self._inside_json_ld = False
        self._json_ld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attributes = dict(attrs)

        if tag == "meta":
            name = (
                attributes.get("name")
                or attributes.get("property")
                or attributes.get("itemprop")
            )

            content = attributes.get("content")

            if name and content:
                self.metadata[name.lower()] = content.strip()

        if tag == "script":
            script_type = (
                attributes.get("type") or ""
            ).lower()

            self._inside_json_ld = (
                script_type == "application/ld+json"
            )

            self._json_ld_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._inside_json_ld:
            content = "".join(self._json_ld_parts).strip()

            if content:
                self.json_ld_blocks.append(content)

            self._inside_json_ld = False
            self._json_ld_parts = []

    def handle_data(self, data: str) -> None:
        if self._inside_json_ld:
            self._json_ld_parts.append(data)


def _clean_value(value: Any) -> str | None:
    """Convert a structured value into a clean string."""

    if value is None:
        return None

    if isinstance(value, (str, int, float)):
        result = str(value).strip()

        return result or None

    return None


def _extract_address_object(
    value: Any,
) -> dict[str, str] | None:
    """Extract a Schema.org PostalAddress object."""

    if isinstance(value, list):
        for item in value:
            result = _extract_address_object(item)

            if result:
                return result

        return None

    if not isinstance(value, dict):
        return None

    address_type = value.get("@type")

    if isinstance(address_type, list):
        address_type = " ".join(
            str(item) for item in address_type
        )

    address_type = str(address_type or "").lower()

    address_fields = {
        "street_address": "streetAddress",
        "city": "addressLocality",
        "state": "addressRegion",
        "postal_code": "postalCode",
        "country": "addressCountry",
    }

    result: dict[str, str] = {}

    for output_key, source_key in address_fields.items():
        raw_value = value.get(source_key)

        if isinstance(raw_value, dict):
            raw_value = (
                raw_value.get("name")
                or raw_value.get("@id")
            )

        cleaned = _clean_value(raw_value)

        if cleaned:
            result[output_key] = cleaned

    if not result:
        return None

    if (
        "postaladdress" not in address_type
        and not any(
            key in result
            for key in ("street_address", "city", "postal_code")
        )
    ):
        return None

    result["source_type"] = "json_ld"

    return result


def _walk_json_ld(value: Any) -> list[dict[str, str]]:
    """Walk JSON-LD objects and find address information."""

    results: list[dict[str, str]] = []

    if isinstance(value, list):
        for item in value:
            results.extend(_walk_json_ld(item))

        return results

    if not isinstance(value, dict):
        return results

    address = value.get("address")

    if address:
        extracted = _extract_address_object(address)

        if extracted:
            results.append(extracted)

    # Also support a PostalAddress object used directly.
    direct = _extract_address_object(value)

    if direct:
        results.append(direct)

    for key in ("@graph", "mainEntity", "location"):
        nested = value.get(key)

        if nested:
            results.extend(_walk_json_ld(nested))

    return results


def _extract_json_ld_locations(
    blocks: list[str],
) -> list[dict[str, str]]:
    """Parse JSON-LD blocks safely."""

    results: list[dict[str, str]] = []

    for block in blocks:
        try:
            parsed = json.loads(block)
        except (json.JSONDecodeError, TypeError):
            continue

        results.extend(_walk_json_ld(parsed))

    return results


def _extract_meta_location(
    metadata: dict[str, str],
) -> dict[str, str] | None:
    """Build a location object from supported meta tags."""

    if not isinstance(metadata, dict):
        return None

    result: dict[str, str] = {}

    mapping = {
        "geo.placename": "city",
        "og:locality": "city",
        "og:region": "state",
        "og:country-name": "country",
        "business:contact_data:locality": "city",
        "business:contact_data:region": "state",
        "business:contact_data:country_name": "country",
        "address": "full_address",
    }

    for source_key, output_key in mapping.items():
        value = metadata.get(source_key)

        if value:
            result[output_key] = str(value).strip()

    if not result:
        return None

    result["source_type"] = "meta_tags"

    return result


def _extract_address_from_text(
    text: str,
) -> list[dict[str, str]]:
    """
    Find explicit address-like lines.

    This deliberately avoids guessing a city or country from
    arbitrary words in website copy.
    """

    if not isinstance(text, str) or not text.strip():
        return []

    results: list[dict[str, str]] = []

    lines = re.split(r"[\n\r]+|(?<=[.!?])\s+", text)

    address_pattern = re.compile(
        r"""
        \b
        (?:address|headquarters|head office|corporate office)
        \s*[:\-]\s*
        (.{8,180})
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    for line in lines:
        cleaned = re.sub(r"\s+", " ", line).strip()

        if not cleaned:
            continue

        match = address_pattern.search(cleaned)

        if not match:
            continue

        address = match.group(1).strip(" ,.;")

        if len(address) < 8:
            continue

        results.append({
            "full_address": address,
            "source_type": "website_text",
        })

    return results


def _location_key(location: dict[str, str]) -> tuple:
    """Create a stable key for duplicate removal."""

    keys = (
        "street_address",
        "full_address",
        "city",
        "state",
        "postal_code",
        "country",
    )

    return tuple(
        str(location.get(key) or "").casefold().strip()
        for key in keys
    )


def extract_location_details(
    html: str = "",
    text: str = "",
) -> list[dict[str, str]]:
    """Extract location records from one page."""

    parser = LocationHTMLParser()

    if html:
        try:
            parser.feed(html)
            parser.close()
        except Exception:
            pass

    results: list[dict[str, str]] = []

    results.extend(
        _extract_json_ld_locations(
            parser.json_ld_blocks
        )
    )

    meta_location = _extract_meta_location(
        parser.metadata
    )

    if meta_location:
        results.append(meta_location)

    results.extend(
        _extract_address_from_text(text)
    )

    unique: list[dict[str, str]] = []
    seen: set[tuple] = set()

    for item in results:
        key = _location_key(item)

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique


def extract_from_pages(
    pages: Iterable[dict[str, Any]],
    max_results: int = 50,
) -> list[dict[str, str]]:
    """
    Extract location information across crawler pages.

    Expected page structure:
        {
            "url": "...",
            "html": "...",
            "text": "..."
        }
    """

    collected: list[dict[str, str]] = []
    seen: set[tuple] = set()

    for page in pages:
        if not isinstance(page, dict):
            continue

        html = str(page.get("html") or "")
        text = str(page.get("text") or "")
        url = str(page.get("url") or "")

        details = extract_location_details(
            html=html,
            text=text,
        )

        for item in details:
            record = dict(item)
            record["source_url"] = url

            key = _location_key(record)

            if key in seen:
                continue

            seen.add(key)
            collected.append(record)

            if len(collected) >= max_results:
                return collected

    return collected


def build_location_summary(
    locations: list[dict[str, str]],
) -> dict[str, Any]:
    """Build a standardized location intelligence result."""

    valid_locations = [
        item
        for item in locations
        if isinstance(item, dict)
    ]

    primary = valid_locations[0] if valid_locations else {}

    return {
        "primary_location": primary or None,
        "locations": valid_locations,
        "location_count": len(valid_locations),
        "detection_status": (
            "detected"
            if valid_locations
            else "not_detected"
        ),
        "verification": "public_website_content_only",
    }
