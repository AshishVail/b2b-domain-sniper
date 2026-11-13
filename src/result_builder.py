"""
b2b-domain-sniper
File: src/result_builder.py

Final Business Intelligence Result Builder.

Features:
- Structured JSON output
- Module result aggregation
- Business information
- Email intelligence
- DNS validation
- Technology intelligence
- Hiring intelligence
- Intent scoring
- Scan metadata
- Error reporting
"""

from __future__ import annotations

import json

from datetime import datetime, timezone
from typing import Any


OUTPUT_VERSION = "1.0"


def utc_now() -> str:
    """Return current UTC timestamp."""

    return datetime.now(
        timezone.utc
    ).isoformat()


def safe_dict(
    value: Any,
) -> dict[str, Any]:
    """Return dictionary or an empty dictionary."""

    if isinstance(value, dict):
        return value

    return {}


def safe_list(
    value: Any,
) -> list[Any]:
    """Return list or an empty list."""

    if isinstance(value, list):
        return value

    return []


def build_business_info(
    data: dict[str, Any],
) -> dict[str, Any]:
    """Build business identity section."""

    business = safe_dict(
        data.get("business")
    )

    return {
        "name": business.get("name"),
        "domain": business.get("domain"),
        "website": business.get("website"),
        "description": business.get("description"),
        "industry": business.get("industry"),
        "location": business.get("location"),
        "phone": business.get("phone"),
    }


def build_email_section(
    data: dict[str, Any],
) -> dict[str, Any]:
    """Build email intelligence section."""

    emails = safe_list(
        data.get("emails")
    )

    unique_emails = []
    seen = set()

    for item in emails:

        if isinstance(item, str):
            email = item.strip().lower()
            details = {
                "email": email,
                "type": "unknown",
            }

        elif isinstance(item, dict):
            details = dict(item)

            email = str(
                details.get("email") or ""
            ).strip().lower()

            details["email"] = email

        else:
            continue

        if not email or email in seen:
            continue

        seen.add(email)
        unique_emails.append(details)

    return {
        "total": len(unique_emails),
        "results": unique_emails,
    }


def build_website_section(
    data: dict[str, Any],
) -> dict[str, Any]:
    """Build website crawl information."""

    website = safe_dict(
        data.get("website")
    )

    pages = safe_list(
        website.get("pages")
    )

    return {
        "url": website.get("url"),
        "reachable": website.get("reachable"),
        "status_code": website.get("status_code"),
        "pages_analyzed": website.get(
            "pages_analyzed",
            len(pages),
        ),
        "pages": pages,
    }


def build_mx_section(
    data: dict[str, Any],
) -> dict[str, Any]:
    """Build MX validation section."""

    return safe_dict(
        data.get("mx_validation", data.get("mx"))
    )


def build_technology_section(
    data: dict[str, Any],
) -> dict[str, Any]:
    """Build technology intelligence section."""

    technology = safe_dict(
        data.get("technology")
    )

    return {
        "technology_count": technology.get(
            "technology_count",
            len(technology.get("technologies", [])),
        ),
        "technologies": safe_list(
            technology.get("technologies")
        ),
        "categories": safe_dict(
            technology.get("categories")
        ),
        "detection_status": technology.get(
            "detection_status"
        ),
    }


def build_hiring_section(
    data: dict[str, Any],
) -> dict[str, Any]:
    """Build hiring intelligence section."""

    hiring = safe_dict(
        data.get("hiring")
    )

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
        "verification": hiring.get(
            "verification",
            "public_website_signals_only",
        ),
    }


def build_intent_section(
    data: dict[str, Any],
) -> dict[str, Any]:
    """Build business intent scoring section."""

    intent = safe_dict(
        data.get("intent")
    )

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
    }


def build_result(
    domain_or_data: Any,
    domain_data: Any = None,
    config: Any = None,
) -> dict[str, Any]:
    """
    Build the final standardized API response.
    Supports both single-argument (data dict) and multi-argument calls.
    """
    # अगर main.py से 3 आर्ग्यूमेंट आए हैं, तो उन्हें मिलाकर एक डेटा डिक्शनरी बना लो
    if domain_data is not None:
        if isinstance(domain_data, dict):
            data = dict(domain_data)
        else:
            data = {}
        data["domain"] = domain_or_data
    else:
        if not isinstance(domain_or_data, dict):
            raise TypeError("Result input must be a dictionary or valid data")
        data = domain_or_data

    errors = safe_list(
        data.get("errors")
    )

    result = {
        "success": not bool(errors),

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
            "status": data.get(
                "status",
                "completed",
            ),
        },

        "business": build_business_info(data),

        "website": build_website_section(data),

        "email_intelligence": build_email_section(data),

        "mx_validation": build_mx_section(data),

        "technology_intelligence": build_technology_section(data),

        "hiring_intelligence": build_hiring_section(data),

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
    """Build and serialize final JSON response."""

    result = build_result(data)

    return serialize_result(
        result,
        pretty=pretty,
    )
