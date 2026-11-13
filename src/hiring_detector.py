
"""
b2b-domain-sniper
File: src/hiring_detector.py

Business Hiring Intelligence Engine.

Features:
- Careers page detection
- Hiring keyword analysis
- Job board detection
- Application link extraction
- Hiring signal scoring
- Multi-page analysis
"""

from __future__ import annotations

import re

from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse


CAREER_PATHS = {
    "/careers",
    "/career",
    "/jobs",
    "/job",
    "/join-us",
    "/join-our-team",
    "/work-with-us",
    "/employment",
    "/opportunities",
    "/vacancies",
    "/open-positions",
    "/about/careers",
}


HIRING_KEYWORDS = {

    "we are hiring": 5,
    "now hiring": 5,
    "join our team": 4,
    "careers": 3,
    "career opportunities": 4,
    "open positions": 5,
    "job openings": 5,
    "current openings": 4,
    "job opportunities": 4,
    "apply now": 3,
    "apply today": 3,
    "send your resume": 4,
    "submit your resume": 4,
    "employment opportunities": 4,
    "multiple positions": 4,
    "talent acquisition": 2,
    "recruitment": 2,
    "recruiting": 2,
    "full-time position": 3,
    "part-time position": 3,
    "remote position": 2,

}


JOB_BOARD_DOMAINS = {

    "greenhouse.io": "Greenhouse",
    "lever.co": "Lever",
    "ashbyhq.com": "Ashby",
    "workday.com": "Workday",
    "myworkdayjobs.com": "Workday",
    "smartrecruiters.com": "SmartRecruiters",
    "bamboohr.com": "BambooHR",
    "jobvite.com": "Jobvite",
    "workable.com": "Workable",
    "icims.com": "iCIMS",
    "recruitee.com": "Recruitee",
    "teamtailor.com": "Teamtailor",

}


class HiringHTMLParser(HTMLParser):
    """Extract website text and anchor links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)

        self.text_parts: list[str] = []

        self.links: list[dict[str, str]] = []

        self.current_link: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:

        if tag.lower() != "a":
            return

        attributes = dict(attrs)

        href = attributes.get("href", "")

        if href:

            self.current_link = {
                "href": href,
                "text": "",
            }

    def handle_data(self, data: str) -> None:

        if data.strip():
            self.text_parts.append(data.strip())

        if self.current_link is not None:
            self.current_link["text"] += " " + data.strip()

    def handle_endtag(self, tag: str) -> None:

        if tag.lower() == "a" and self.current_link:

            self.links.append(
                self.current_link
            )

            self.current_link = None


def normalize_url(url: str) -> str:
    """Normalize URLs for duplicate filtering."""

    parsed = urlparse(url)

    return (
        f"{parsed.scheme}://{parsed.netloc}"
        f"{parsed.path.rstrip('/') or '/'}"
    )


def is_career_path(url: str) -> bool:
    """Identify common recruitment URL paths."""

    path = urlparse(url).path.lower().rstrip("/")

    return (
        path in CAREER_PATHS
        or any(
            path.endswith(item)
            for item in CAREER_PATHS
        )
        or bool(
            re.search(
                r"/(careers?|jobs?|vacancies|open-positions)(/|$)",
                path,
            )
        )
    )


def detect_job_board(url: str) -> str | None:
    """Identify external recruitment platforms."""

    hostname = (
        urlparse(url).hostname or ""
    ).lower()

    for domain, provider in JOB_BOARD_DOMAINS.items():

        if (
            hostname == domain
            or hostname.endswith("." + domain)
        ):
            return provider

    return None


def detect_hiring(
    html: str = "",
    text: str = "",
    page_url: str = "",
) -> dict[str, Any]:
    """
    Analyze a website page for public hiring signals.

    This detects recruitment indicators.
    It does not guarantee active vacancies.
    """

    parser = HiringHTMLParser()

    if html:

        try:
            parser.feed(html)

        except Exception:
            pass

    page_text = " ".join([
        text or "",
        " ".join(parser.text_parts),
    ])

    searchable = re.sub(
        r"\s+",
        " ",
        page_text,
    ).lower()

    matched_keywords = []

    score = 0

    # Keyword detection
    for keyword, weight in HIRING_KEYWORDS.items():

        if keyword in searchable:

            matched_keywords.append({
                "keyword": keyword,
                "weight": weight,
            })

            score += weight

    career_links = []

    job_board_links = []

    # Link analysis
    for link in parser.links:

        href = link["href"].strip()

        if not href:
            continue

        if href.startswith((
            "#",
            "mailto:",
            "tel:",
            "javascript:",
        )):
            continue

        absolute_url = urljoin(
            page_url,
            href,
        )

        parsed = urlparse(absolute_url)

        if parsed.scheme not in {"http", "https"}:
            continue

        link_text = link["text"].strip()

        provider = detect_job_board(
            absolute_url
        )

        if provider:

            job_board_links.append({
                "url": absolute_url,
                "provider": provider,
                "text": link_text,
            })

            score += 5

        if (
            is_career_path(absolute_url)
            or re.search(
                r"\b(careers?|jobs?|apply|vacancies|positions)\b",
                link_text,
                re.IGNORECASE,
            )
        ):

            career_links.append({
                "url": normalize_url(absolute_url),
                "text": link_text,
            })

            score += 3

    # Remove duplicate links
    career_links = list({
        item["url"]: item
        for item in career_links
    }.values())

    job_board_links = list({
        item["url"]: item
        for item in job_board_links
    }.values())

    score = min(score, 100)

    if score >= 12:
        status = "strong_hiring_signals"

    elif score >= 5:
        status = "possible_hiring_activity"

    else:
        status = "no_clear_hiring_signal"

    return {
        "hiring_score": score,
        "hiring_status": status,
        "hiring_detected": score >= 5,
        "matched_keywords": matched_keywords,
        "career_links": career_links,
        "job_board_links": job_board_links,
        "evidence_count": (
            len(matched_keywords)
            + len(career_links)
            + len(job_board_links)
        ),
        "source_url": page_url,
        "verification": "public_website_signals_only",
    }


def detect_hiring_from_pages(
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate hiring signals across multiple website pages."""

    all_keywords: dict[str, dict[str, Any]] = {}

    all_career_links: dict[str, dict[str, str]] = {}

    all_job_boards: dict[str, dict[str, str]] = {}

    page_results = []

    for page in pages:

        if not isinstance(page, dict):
            continue

        result = detect_hiring(
            html=str(page.get("html") or ""),
            text=str(page.get("text") or ""),
            page_url=str(page.get("url") or ""),
        )

        page_results.append(result)

        for item in result["matched_keywords"]:
            all_keywords[item["keyword"]] = item

        for item in result["career_links"]:
            all_career_links[item["url"]] = item

        for item in result["job_board_links"]:
            all_job_boards[item["url"]] = item

    total_score = sum(
        item["weight"]
        for item in all_keywords.values()
    )

    total_score += len(all_career_links) * 3

    total_score += len(all_job_boards) * 5

    total_score = min(total_score, 100)

    if total_score >= 12:
        status = "strong_hiring_signals"

    elif total_score >= 5:
        status = "possible_hiring_activity"

    else:
        status = "no_clear_hiring_signal"

    return {
        "hiring_score": total_score,
        "hiring_status": status,
        "hiring_detected": total_score >= 5,
        "matched_keywords": list(
            all_keywords.values()
        ),
        "career_links": list(
            all_career_links.values()
        ),
        "job_board_links": list(
            all_job_boards.values()
        ),
        "pages_analyzed": len(page_results),
        "page_results": page_results,
        "verification": "public_website_signals_only",
    }
