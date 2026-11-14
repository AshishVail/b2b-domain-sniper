"""Extract publicly displayed email addresses from website pages.

The extractor normalizes addresses, rejects malformed candidates, handles
common textual obfuscation, and preserves the source page for each result.
It does not verify mailbox existence or deliverability.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import unquote

EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])"
    r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@"
    r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+"
    r"(?![\w-])",
    re.IGNORECASE,
)

OBFUSCATION_PATTERNS = (
    (re.compile(r"\s*(?:\[at\]|\(at\))\s*", re.I), "@"),
    (re.compile(r"\s+at\s+", re.I), "@"),
    (re.compile(r"\s*(?:\[dot\]|\(dot\))\s*", re.I), "."),
    (re.compile(r"\s+dot\s+", re.I), "."),
)

INVALID_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".ico",
}

ROLE_ACCOUNTS = {
    "info", "contact", "hello", "support", "sales", "admin",
    "office", "enquiries", "inquiries", "marketing", "business",
    "careers", "jobs", "hr", "billing", "service", "team",
}

IGNORED_TAGS = {"script", "style", "noscript", "svg", "template"}


class EmailHTMLParser(HTMLParser):
    """Collect visible text and mailto links while ignoring code/style blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.mailto_addresses: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attributes = dict(attrs)

        if tag in IGNORED_TAGS:
            self._ignored_depth += 1
            return

        if self._ignored_depth:
            return

        if tag == "a":
            href = attributes.get("href") or ""
            if href.lower().startswith("mailto:"):
                raw = unquote(href[7:]).split("?", 1)[0]
                self.mailto_addresses.extend(
                    part.strip()
                    for part in raw.split(",")
                    if part.strip()
                )

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.text_parts.append(data.strip())


def _valid_domain(domain: str) -> bool:
    if not domain or len(domain) > 253 or "." not in domain:
        return False

    try:
        ascii_domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        return False

    labels = ascii_domain.rstrip(".").split(".")

    if len(labels) < 2:
        return False

    return all(
        1 <= len(label) <= 63
        and re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?",
            label,
        )
        for label in labels
    )


def _is_valid_candidate(email: str) -> bool:
    if not email or len(email) > 254 or email.count("@") != 1:
        return False

    local, domain = email.rsplit("@", 1)

    if not local or len(local) > 64 or not _valid_domain(domain):
        return False

    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False

    if any(domain.endswith(ext) for ext in INVALID_EXTENSIONS):
        return False

    if any(char.isspace() for char in email):
        return False

    return True


def normalize_email(email: str) -> str | None:
    """Return a normalized valid email, or None for invalid input."""
    if not isinstance(email, str):
        return None

    candidate = email.strip().strip(".,;:<>[](){}\"'").lower()

    return candidate if _is_valid_candidate(candidate) else None


def _repair_obfuscated(text: str) -> str:
    for pattern, replacement in OBFUSCATION_PATTERNS:
        text = pattern.sub(replacement, text)

    return text


def extract_emails(
    html: str = "",
    text: str = "",
    include_obfuscated: bool = True,
    max_results: int = 100,
) -> list[str]:
    """Extract unique valid email addresses from HTML and plain text."""
    if max_results <= 0:
        return []

    parser = EmailHTMLParser()

    if isinstance(html, str) and html:
        try:
            parser.feed(html)
            parser.close()
        except Exception:
            pass

    visible_text = " ".join(parser.text_parts)

    searchable = "\n".join(
        value
        for value in (
            visible_text,
            text if isinstance(text, str) else "",
        )
        if value
    )

    if include_obfuscated:
        searchable = _repair_obfuscated(searchable)

    candidates = list(parser.mailto_addresses)
    candidates.extend(EMAIL_PATTERN.findall(searchable))

    results: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        normalized = normalize_email(candidate)

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        results.append(normalized)

        if len(results) >= max_results:
            break

    return results


def classify_email(email: str) -> str:
    """Classify an address as role-based or personal/other."""
    local = email.split("@", 1)[0].lower()

    return (
        "role_based"
        if local in ROLE_ACCOUNTS
        else "personal_or_other"
    )


def extract_email_details(
    html: str = "",
    text: str = "",
) -> list[dict[str, str]]:
    return [
        {
            "email": email,
            "type": classify_email(email),
            "source_type": "website_content",
        }
        for email in extract_emails(html=html, text=text)
    ]


def extract_from_pages(
    pages: Iterable[dict],
    max_results: int = 200,
) -> list[dict[str, str]]:
    """Extract and deduplicate email addresses across crawler pages."""
    if max_results <= 0:
        return []

    collected: dict[str, dict[str, str]] = {}

    for page in pages:
        if not isinstance(page, dict):
            continue

        html = str(page.get("html") or "")
        text = str(page.get("text") or "")
        url = str(page.get("url") or "")

        for email in extract_emails(html=html, text=text):
            collected.setdefault(
                email,
                {
                    "email": email,
                    "type": classify_email(email),
                    "source_url": url,
                    "source_type": "website_content",
                },
            )

            if len(collected) >= max_results:
                return list(collected.values())

    return list(collected.values())
