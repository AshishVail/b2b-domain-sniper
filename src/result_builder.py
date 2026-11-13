
"""
B2B Domain Sniper
Final Business Intelligence Result Builder.
"""

from __future__ import annotations

import json

from datetime import datetime, timezone
from typing import Any


OUTPUT_VERSION = "1.1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def build_business_info(data: dict) -> dict:
    """Build business identity."""

    business = safe_dict(data.get("business"))

    return {
        "name": business.get("name"),
        "domain": business.get("domain") or data.get("domain"),
        "website": business.get("website") or data.get("website_url"),
        "description": business.get("description"),
        "industry": business.get("industry"),
        "location": business.get("location"),
        "phone": business.get("phone"),
    }


def build_email_section(data: dict) -> dict:
    """Build email intelligence."""

    emails = safe_list(data.get("emails"))

    unique_emails = []
    seen = set()

    for item in emails:

        if isinstance(item, str):
            details = {
                "email": item,
                "type": "unknown",
            }

        elif isinstance(item, dict):
            details = dict(item)

        else:
            continue

        email = str(
            details.get("email") or ""
        ).strip().lower()

        if not email or email in seen:
            continue

        seen.add(email)

        details["email"] = email

        unique_emails.append(details)

    return {
        "total": len(unique_emails),
        "results": unique_emails,
    }


def build_website_section(data: dict) -> dict:
    """Build website crawl information."""

    website = safe_dict(data.get("website"))

    # Support both nested and original crawler output
    pages = safe_list(
        website.get("pages", data.get("pages"))
    )

    homepage = pages[0] if pages else {}

    return {
        "url": (
            website.get("url")
            or data.get("website_url")
        ),
        "reachable": website.get(
            "reachable",
            bool(homepage.get("html")),
        ),
        "status_code": website.get(
            "status_code",
            homepage.get("status_code"),
        ),
        "pages_analyzed": website.get(
            "pages_analyzed",
            data.get("page_count", len(pages)),
        ),
        "pages": pages,
    }


def build_mx_section(data: dict) -> dict:
    """Build email server validation."""

    return safe_dict(
        data.get(
            "mx_validation",
            data.get("mx"),
        )
    )


def build_technology_section(data: dict) -> dict:
    """Build technology detection results."""

    technology = safe_dict(
        data.get(
            "technology",
            data.get("technologies"),
        )
    )

    technologies = safe_list(
        technology.get("technologies")
    )

    return {
        "technology_count": technology.get(
            "technology_count",
            len(technologies),
        ),
        "technologies": technologies,
        "categories": safe_dict(
            technology.get("categories")
        ),
        "pages_analyzed": technology.get(
            "pages_analyzed",
            0,
        ),
        "detection_status": technology.get(
            "detection_status",
            "not_available",
        ),
    }


def build_hiring_section(data: dict) -> dict:
    """Build hiring intelligence."""

    hiring = safe_dict(data.get("hiring"))

    return {
        "hiring_detected": hiring.get(
            "hiring_detected",
            False,
        ),
        "hiring_score": hiring.get(
            "hiring_score",
            0,
        ),
        "hiring_status": hiring.get(
            "hiring_status",
            "unknown",
        ),
        "matched_keywords": safe_list(
            hiring.get("matched_keywords")
        ),
        "career_links": safe_list(
            hiring.get("career_links")
        ),
        "job_board_links": safe_list(
            hiring.get("job_board_links")
        ),
        "pages_analyzed": hiring.get(
            "pages_analyzed",
            0,
        ),
        "verification": hiring.get(
            "verification",
            "public_website_signals_only",
        ),
    }


def build_intent_section(data: dict) -> dict:
    """Build business intent score."""

    intent = safe_dict(data.get("intent"))

    return {
        "intent_score": intent.get(
            "intent_score",
            0,
        ),
        "intent_level": intent.get(
            "intent_level",
            "unknown",
        ),
        "lead_quality": intent.get(
            "lead_quality",
            "unknown",
        ),
        "score_breakdown": safe_dict(
            intent.get("score_breakdown")
        ),
        "signals_analyzed": intent.get(
            "signals_analyzed",
            0,
        ),
        "available_signals": safe_list(
            intent.get("available_signals")
        ),
    }


def build_result(
    domain_or_data: Any,
    domain_data: Any = None,
    config: Any = None,
) -> dict[str, Any]:
    """
    Build final standardized JSON.

    Supports:
    build_result(data)
    build_result(domain, data, config)
    """

    if domain_data is not None:

        if not isinstance(domain_data, dict):
            raise TypeError(
                "domain_data must be a dictionary."
            )

        data = dict(domain_data)

        data["domain"] = (
            data.get("domain")
            or domain_or_data
        )

    else:

        if not isinstance(domain_or_data, dict):
            raise TypeError(
                "Input must be a dictionary."
            )

        data = dict(domain_or_data)

    errors = safe_list(data.get("errors"))

    status = data.get(
        "status",
        "completed",
    )

    # Partial page errors do not automatically mean
    # the complete domain scan failed.
    success = status == "completed"

    result = {
        "success": success,

        "api": {
            "name": "b2b-domain-sniper",
            "version": OUTPUT_VERSION,
        },

        "scan": {
            "scan_id": data.get("scan_id"),
            "timestamp": data.get(
                "timestamp",
                utc_now(),
            ),
            "domain": data.get("domain"),
            "status": status,
        },

        "business": build_business_info(data),

        "website": build_website_section(data),

        "email_intelligence": build_email_section(data),

        "mx_validation": build_mx_section(data),

        "technology_intelligence": (
            build_technology_section(data)
        ),

        "hiring_intelligence": (
            build_hiring_section(data)
        ),

        "business_intelligence": {
            "intent": build_intent_section(data),
        },

        "errors": errors,
    }

    return result


def serialize_result(
    result: dict[str, Any],
    pretty: bool = False,
) -> str:
    """Serialize result into JSON."""

    return json.dumps(
        result,
        ensure_ascii=False,
        indent=2 if pretty else None,
        default=str,
    )


def build_json_result(
    data: dict[str, Any],
    pretty: bool = False,
) -> str:
    """Build and serialize final JSON."""

    result = build_result(data)

    return serialize_result(
        result,
        pretty=pretty,
    )
