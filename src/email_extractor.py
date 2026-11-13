
"""
b2b-domain-sniper
File: src/email_extractor.py

Extract business email addresses from website HTML and text.
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
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+",
    re.IGNORECASE,
)

OBFUSCATION_PATTERNS = [
    (re.compile(r"\s*\[at\]\s*", re.I), "@"),
    (re.compile(r"\s*\(at\)\s*", re.I), "@"),
    (re.compile(r"\s+at\s+", re.I), "@"),
    (re.compile(r"\s*\[dot\]\s*", re.I), "."),
    (re.compile(r"\s*\(dot\)\s*", re.I), "."),
    (re.compile(r"\s+dot\s+", re.I), "."),
]

INVALID_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".svg", ".css", ".js", ".woff", ".woff2",
}

ROLE_ACCOUNTS = {
    "info", "contact", "hello", "support", "sales",
    "admin", "office", "enquiries", "inquiries",
    "marketing", "business", "careers", "jobs",
    "hr", "billing", "service", "team",
}


class EmailHTMLParser(HTMLParser):
    """Collect visible text and mailto links from HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.mailto_addresses: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text_parts.append(data)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return

        for key, value in attrs:
            if key.lower() == "href" and value:
                if value.lower().startswith("mailto:"):
                    address = unquote(value[7:].split("?")[0])
                    self.mailto_addresses.append(address)


def normalize_email(email: str) -> str:
    """Normalize an email address without changing its local-part case."""

    return email.strip().strip(".,;:<>[](){}\"'").lower()


def _repair_obfuscated(text: str) -> str:
    for pattern, replacement in OBFUSCATION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _is_valid_candidate(email: str) -> bool:
    if len(email) > 254 or email.count("@") != 1:
        return False

    local, domain = email.rsplit("@", 1)

    if not local or len(local) > 64:
        return False

    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False

    if "." not in domain:
        return False

    if any(domain.endswith(ext) for ext in INVALID_EXTENSIONS):
        return False

    if domain.startswith(".") or domain.endswith("."):
        return False

    return True


def extract_emails(
    html: str = "",
    text: str = "",
    include_obfuscated: bool = True,
    max_results: int = 100,
) -> list[str]:
    """
    Extract unique email addresses from HTML and plain text.

    Returns:
        List of normalized email addresses.
    """

    parser = EmailHTMLParser()

    if html:
        try:
            parser.feed(html)
        except Exception:
            pass

    searchable = "\n".join(
        [html, text, " ".join(parser.text_parts)]
    )

    if include_obfuscated:
        searchable = _repair_obfuscated(searchable)

    candidates = list(parser.mailto_addresses)
    candidates.extend(EMAIL_PATTERN.findall(searchable))

    results: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        email = normalize_email(candidate)

        if not _is_valid_candidate(email):
            continue

        if email in seen:
            continue

        seen.add(email)
        results.append(email)

        if len(results) >= max_results:
            break

    return results


def classify_email(email: str) -> str:
    """Classify an address as role-based or personal-style."""

    local = email.split("@", 1)[0].lower()

    if local in ROLE_ACCOUNTS:
        return "role_based"

    return "personal_or_other"


def extract_email_details(
    html: str = "",
    text: str = "",
) -> list[dict[str, str]]:
    """Return email addresses with basic classification."""

    emails = extract_emails(html=html, text=text)

    return [
        {
            "email": email,
            "type": classify_email(email),
            "source_type": "website_content",
        }
        for email in emails
    ]


def extract_from_pages(
    pages: Iterable[dict],
    max_results: int = 200,
) -> list[dict[str, str]]:
    """Extract and deduplicate emails across crawler page results."""

    collected: dict[str, dict[str, str]] = {}

    for page in pages:
        if not isinstance(page, dict):
            continue

        html = str(page.get("html") or "")
        text = str(page.get("text") or "")
        url = str(page.get("url") or "")

        for email in extract_emails(html=html, text=text):
            if email not in collected:
                collected[email] = {
                    "email": email,
                    "type": classify_email(email),
                    "source_url": url,
                    "source_type": "website_content",
                }

            if len(collected) >= max_results:
                return list(collected.values())

    return list(collected.values())
