
"""
b2b-domain-sniper
File: src/content_cleaner.py

Website Content Cleaning and Normalization Engine.

Features:
- HTML parsing
- Script and style removal
- Text extraction
- Metadata extraction
- URL normalization
- Duplicate text removal
- Clean crawler output
"""

from __future__ import annotations

import re

from html.parser import HTMLParser
from typing import Any
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)


IGNORED_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "template",
}


TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "ref",
    "source",
}


class WebsiteHTMLParser(HTMLParser):
    """Extract visible text, links and metadata from HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)

        self.text_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self.metadata: dict[str, str] = {}

        self.title = ""

        self._ignored_depth = 0
        self._inside_title = False

        self._current_link: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:

        tag = tag.lower()
        attributes = dict(attrs)

        if tag in IGNORED_TAGS:
            self._ignored_depth += 1
            return

        if self._ignored_depth:
            return

        if tag == "title":
            self._inside_title = True

        if tag == "meta":

            name = (
                attributes.get("name")
                or attributes.get("property")
                or attributes.get("http-equiv")
            )

            content = attributes.get("content")

            if name and content:
                self.metadata[name.lower()] = content.strip()

        if tag == "a":

            href = attributes.get("href", "")

            if href:
                self._current_link = {
                    "href": href.strip(),
                    "text": "",
                }

    def handle_endtag(self, tag: str) -> None:

        tag = tag.lower()

        if tag in IGNORED_TAGS:

            if self._ignored_depth > 0:
                self._ignored_depth -= 1

            return

        if self._ignored_depth:
            return

        if tag == "title":
            self._inside_title = False

        if tag == "a" and self._current_link:

            self.links.append(self._current_link)
            self._current_link = None

    def handle_data(self, data: str) -> None:

        if self._ignored_depth:
            return

        if not data.strip():
            return

        cleaned = data.strip()

        self.text_parts.append(cleaned)

        if self._inside_title:
            self.title += " " + cleaned

        if self._current_link is not None:
            self._current_link["text"] += " " + cleaned


def normalize_text(text: str) -> str:
    """Normalize whitespace and invisible characters."""

    if not isinstance(text, str):
        return ""

    text = text.replace("\x00", "")
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")

    text = re.sub(r"[\t\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def remove_duplicate_lines(
    text: str,
) -> str:
    """Remove repeated non-empty lines while preserving order."""

    seen = set()
    results = []

    for line in text.splitlines():

        line = normalize_text(line)

        if not line:
            continue

        key = line.casefold()

        if key in seen:
            continue

        seen.add(key)
        results.append(line)

    return "\n".join(results)


def clean_html(
    html: str,
) -> dict[str, Any]:
    """Parse HTML and return clean visible content."""

    if not isinstance(html, str):
        html = ""

    parser = WebsiteHTMLParser()

    try:
        parser.feed(html)
        parser.close()

    except Exception:
        pass

    text = normalize_text(
        " ".join(parser.text_parts)
    )

    title = normalize_text(parser.title)

    links = []

    for link in parser.links:

        href = link["href"].strip()
        label = normalize_text(link["text"])

        if not href:
            continue

        links.append({
            "url": href,
            "text": label,
        })

    return {
        "title": title,
        "text": text,
        "metadata": parser.metadata,
        "links": links,
        "text_length": len(text),
    }


def normalize_url(
    url: str,
    remove_tracking: bool = True,
) -> str:
    """Normalize URL and optionally remove tracking parameters."""

    if not isinstance(url, str):
        return ""

    url = url.strip()

    try:
        parsed = urlsplit(url)

        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").lower()

        if not hostname:
            return ""

        if scheme not in {"http", "https"}:
            return ""

        if parsed.username or parsed.password:
            return ""

        port = parsed.port

        if port and not (
            (scheme == "http" and port == 80)
            or (scheme == "https" and port == 443)
        ):
            hostname = f"{hostname}:{port}"

        query = parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )

        if remove_tracking:

            query = [
                (key, value)
                for key, value in query
                if key.lower() not in TRACKING_PARAMETERS
                and not key.lower().startswith("utm_")
            ]

        return urlunsplit((
            scheme,
            hostname,
            parsed.path or "/",
            urlencode(query, doseq=True),
            "",
        ))

    except (ValueError, TypeError):
        return ""


def clean_page(
    page: dict[str, Any],
) -> dict[str, Any]:
    """Clean a crawler page dictionary."""

    if not isinstance(page, dict):
        raise TypeError("Page must be a dictionary")

    html = str(page.get("html") or "")

    parsed = clean_html(html)

    existing_text = str(page.get("text") or "")

    if existing_text:
        parsed["text"] = normalize_text(
            existing_text + " " + parsed["text"]
        )

    parsed["url"] = normalize_url(
        str(page.get("url") or "")
    )

    parsed["text"] = remove_duplicate_lines(
        parsed["text"]
    )

    parsed["text_length"] = len(parsed["text"])

    return parsed


def clean_pages(
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Clean and deduplicate multiple crawler pages."""

    results = []
    seen_urls = set()

    for page in pages:

        if not isinstance(page, dict):
            continue

        cleaned = clean_page(page)

        url = cleaned["url"]

        if url and url in seen_urls:
            continue

        if url:
            seen_urls.add(url)

        results.append(cleaned)

    return results


def extract_metadata(
    html: str,
) -> dict[str, str]:
    """Extract title, description and social metadata."""

    result = clean_html(html)

    metadata = result["metadata"]

    return {
        "title": result["title"],
        "description": (
            metadata.get("description")
            or metadata.get("og:description")
            or ""
        ),
        "keywords": metadata.get("keywords", ""),
        "author": metadata.get("author", ""),
        "og_title": metadata.get("og:title", ""),
        "og_description": metadata.get("og:description", ""),
        "og_type": metadata.get("og:type", ""),
    }
