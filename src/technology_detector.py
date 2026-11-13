
"""
b2b-domain-sniper
File: src/technology_detector.py

Website Technology Intelligence Engine.

Features:
- CMS detection
- JavaScript framework detection
- CSS framework detection
- Analytics detection
- Marketing technology detection
- Payment provider detection
- Server and CDN detection
- Confidence and evidence reporting
"""

from __future__ import annotations

import re
from typing import Any


TECHNOLOGY_SIGNATURES: dict[str, dict[str, Any]] = {

    # CMS
    "WordPress": {
        "category": "CMS",
        "patterns": [
            r"wp-content/",
            r"wp-includes/",
            r"wordpress",
        ],
    },

    "Shopify": {
        "category": "Ecommerce",
        "patterns": [
            r"cdn\.shopify\.com",
            r"myshopify\.com",
            r"shopify\.theme",
        ],
    },

    "Wix": {
        "category": "Website Builder",
        "patterns": [
            r"wix\.com",
            r"wixstatic\.com",
            r"_wix_browser_sess",
        ],
    },

    "Squarespace": {
        "category": "Website Builder",
        "patterns": [
            r"squarespace\.com",
            r"squarespace-cdn\.com",
        ],
    },

    "Webflow": {
        "category": "Website Builder",
        "patterns": [
            r"webflow\.com",
            r"webflow\.io",
            r"data-wf-page",
        ],
    },

    "Drupal": {
        "category": "CMS",
        "patterns": [
            r"drupal\.js",
            r"sites/default/files",
            r"drupal-settings-json",
        ],
    },

    "Joomla": {
        "category": "CMS",
        "patterns": [
            r"joomla",
            r"/media/system/js/",
        ],
    },

    # JavaScript frameworks
    "React": {
        "category": "JavaScript Framework",
        "patterns": [
            r"react-dom",
            r"react\.production",
            r"data-reactroot",
        ],
    },

    "Next.js": {
        "category": "JavaScript Framework",
        "patterns": [
            r"_next/static",
            r"__next_data__",
        ],
    },

    "Vue.js": {
        "category": "JavaScript Framework",
        "patterns": [
            r"vue\.js",
            r"vue\.runtime",
            r"data-v-[a-f0-9]+",
        ],
    },

    "Angular": {
        "category": "JavaScript Framework",
        "patterns": [
            r"ng-version",
            r"angular\.js",
        ],
    },

    # CSS frameworks
    "Bootstrap": {
        "category": "CSS Framework",
        "patterns": [
            r"bootstrap\.min\.css",
            r"bootstrap\.css",
        ],
    },

    "Tailwind CSS": {
        "category": "CSS Framework",
        "patterns": [
            r"tailwindcss",
            r"tailwind\.min\.css",
        ],
    },

    # Analytics
    "Google Analytics": {
        "category": "Analytics",
        "patterns": [
            r"google-analytics\.com",
            r"googletagmanager\.com",
            r"gtag\(",
        ],
    },

    "Google Tag Manager": {
        "category": "Tag Manager",
        "patterns": [
            r"googletagmanager\.com/gtm\.js",
            r"GTM-[A-Z0-9]+",
        ],
    },

    "Hotjar": {
        "category": "Analytics",
        "patterns": [
            r"static\.hotjar\.com",
            r"hotjar",
        ],
    },

    # Advertising
    "Meta Pixel": {
        "category": "Advertising",
        "patterns": [
            r"connect\.facebook\.net",
            r"fbq\(",
        ],
    },

    # Payment
    "Stripe": {
        "category": "Payment",
        "patterns": [
            r"js\.stripe\.com",
            r"stripe\.com/v3",
        ],
    },

    # Marketing automation
    "HubSpot": {
        "category": "Marketing Automation",
        "patterns": [
            r"js\.hs-scripts\.com",
            r"hubspot\.com",
            r"hsforms\.net",
        ],
    },

    # Customer support
    "Intercom": {
        "category": "Customer Support",
        "patterns": [
            r"widget\.intercom\.io",
            r"intercomSettings",
        ],
    },

}


HEADER_SIGNATURES = {

    "server": {
        "nginx": "Nginx",
        "apache": "Apache",
        "cloudflare": "Cloudflare",
        "microsoft-iis": "Microsoft IIS",
        "caddy": "Caddy",
    },

    "x-powered-by": {
        "php": "PHP",
        "express": "Express.js",
        "asp.net": "ASP.NET",
        "next.js": "Next.js",
    },

}


def normalize_headers(
    headers: dict[str, Any] | None,
) -> dict[str, str]:
    """Normalize HTTP response headers."""

    if not headers:
        return {}

    return {
        str(key).lower(): str(value)
        for key, value in headers.items()
    }


def match_patterns(
    content: str,
    patterns: list[str],
) -> list[str]:
    """Find matching technology signatures."""

    matches = []

    for pattern in patterns:
        try:
            if re.search(
                pattern,
                content,
                re.IGNORECASE,
            ):
                matches.append(pattern)

        except re.error:
            continue

    return matches


def detect_technologies(
    html: str = "",
    headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Detect website technologies.

    Args:
        html: Website HTML source.
        headers: HTTP response headers.

    Returns:
        Categorized technology intelligence report.
    """

    content = html or ""

    normalized_headers = normalize_headers(headers)

    results: dict[str, dict[str, Any]] = {}

    # HTML-based detection
    for technology, metadata in TECHNOLOGY_SIGNATURES.items():

        matched = match_patterns(
            content,
            metadata["patterns"],
        )

        if matched:
            results[technology] = {
                "name": technology,
                "category": metadata["category"],
                "confidence": "high",
                "evidence": matched,
                "source": "html",
            }

    # HTTP header detection
    for header_name, signatures in HEADER_SIGNATURES.items():

        header_value = normalized_headers.get(
            header_name,
            "",
        ).lower()

        for signature, technology in signatures.items():

            if signature in header_value:

                if technology not in results:
                    results[technology] = {
                        "name": technology,
                        "category": "Server / Runtime",
                        "confidence": "medium",
                        "evidence": [],
                        "source": "http_header",
                    }

                results[technology]["evidence"].append(
                    f"{header_name}: {header_value}"
                )

    technologies = list(results.values())

    categories: dict[str, list[str]] = {}

    for item in technologies:

        category = item["category"]

        categories.setdefault(
            category,
            [],
        ).append(item["name"])

    return {
        "technologies": technologies,
        "technology_count": len(technologies),
        "categories": categories,
        "detection_status": (
            "technologies_found"
            if technologies
            else "no_technologies_detected"
        ),
    }


def detect_from_page(
    page: dict[str, Any],
) -> dict[str, Any]:
    """Detect technologies from one crawler result."""

    if not isinstance(page, dict):
        return detect_technologies()

    return detect_technologies(
        html=str(page.get("html") or ""),
        headers=page.get("headers") or {},
    )


def detect_from_pages(
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate technology findings across multiple pages."""

    combined: dict[str, dict[str, Any]] = {}

    for page in pages:

        result = detect_from_page(page)

        for item in result["technologies"]:

            name = item["name"]

            if name not in combined:
                combined[name] = {
                    **item,
                    "evidence": list(item["evidence"]),
                }

            else:
                existing = combined[name]

                for evidence in item["evidence"]:

                    if evidence not in existing["evidence"]:
                        existing["evidence"].append(evidence)

    technologies = list(combined.values())

    categories: dict[str, list[str]] = {}

    for item in technologies:

        categories.setdefault(
            item["category"],
            [],
        ).append(item["name"])

    return {
        "technologies": technologies,
        "technology_count": len(technologies),
        "categories": categories,
        "pages_analyzed": len(pages),
        "detection_status": (
            "technologies_found"
            if technologies
            else "no_technologies_detected"
        ),
    }
