"""
B2B Domain Sniper
Final Business Intelligence Result Builder.
"""

from __future__ import annotations

import json

from datetime import datetime, timezone
from typing import Any


OUTPUT_VERSION = "1.2"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def safe_string(value: Any) -> str | None:
    """Return a clean non-empty string."""

    if value is None:
        return None

    value = str(value).strip()

    return value or None


def build_business_info(data: dict) -> dict:
    """Build business identity and profile information."""

    business = safe_dict(data.get("business"))

    industry_details = safe_dict(
        business.get("industry_details")
        or data.get("industry")
    )

    location = (
        business.get("location")
        or data.get("location")
    )

    phone_numbers = (
        business.get("phone_numbers")
        or data.get("phone_numbers")
    )

    phone = (
        business.get("phone")
        or _get_primary_phone(phone_numbers)
    )

    description = (
        business.get("description")
        or data.get("business_summary")
    )

    return {
        "name": safe_string(business.get("name")),
        "domain": (
            safe_string(business.get("domain"))
            or safe_string(data.get("domain"))
        ),
        "website": (
            safe_string(business.get("website"))
            or safe_string(data.get("website_url"))
        ),
        "description": safe_string(description),
        "industry": (
            safe_string(business.get("industry"))
            or safe_string(industry_details.get("primary_industry"))
        ),
        "location": location,
        "phone": safe_string(phone),
    }


def _get_primary_phone(phone_numbers: Any) -> str | None:
    """Get the first usable phone number."""

    for item in safe_list(phone_numbers):

        if isinstance(item, str):
            value = safe_string(item)

        elif isinstance(item, dict):
            value = safe_string(item.get("phone"))

        else:
            value = None

        if value:
            return value

    return None


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


def build_phone_section(data: dict) -> dict:
    """Build phone number intelligence."""

    phone_numbers = (
        data.get("phone_numbers")
        or safe_dict(data.get("business")).get("phone_numbers")
    )

    if not phone_numbers:
        primary_phone = safe_dict(
            data.get("business")
        ).get("phone")

        phone_numbers = (
            [{"phone": primary_phone}]
            if primary_phone
            else []
        )

    unique_numbers = []
    seen = set()

    for item in safe_list(phone_numbers):

        if isinstance(item, str):
            details = {
                "phone": item,
            }

        elif isinstance(item, dict):
            details = dict(item)

        else:
            continue

        phone = safe_string(details.get("phone"))

        if not phone:
            continue

        normalized = (
            safe_string(details.get("normalized_digits"))
            or "".join(
                character
                for character in phone
                if character.isdigit()
            )
        )

        deduplication_key = normalized or phone.lower()

        if deduplication_key in seen:
            continue

        seen.add(deduplication_key)

        details["phone"] = phone
        details["normalized_digits"] = normalized

        unique_numbers.append(details)

    return {
        "total": len(unique_numbers),
        "primary_phone": (
            unique_numbers[0]["phone"]
            if unique_numbers
            else None
        ),
        "results": unique_numbers,
        "detection_status": (
            "completed" if unique_numbers else "not_detected"
        ),
    }


def build_industry_section(data: dict) -> dict:
    """Build industry classification intelligence."""

    business = safe_dict(data.get("business"))

    industry = safe_dict(
        data.get("industry")
        or business.get("industry_details")
    )

    primary_industry = (
        industry.get("primary_industry")
        or industry.get("industry")
        or business.get("industry")
    )

    return {
        "primary_industry": safe_string(primary_industry),
        "confidence": industry.get("confidence", 0),
        "candidates": safe_list(
            industry.get("candidates")
        ),
        "matched_keywords": safe_list(
            industry.get("matched_keywords")
        ),
        "detection_status": industry.get(
            "detection_status",
            "not_detected" if not primary_industry else "completed",
        ),
    }


def build_location_section(data: dict) -> dict:
    """Build business location intelligence."""

    business = safe_dict(data.get("business"))

    location_summary = (
        data.get("location")
        or business.get("location")
    )

    locations = (
        data.get("locations")
        or safe_dict(location_summary).get("locations")
    )

    summary = safe_dict(location_summary)

    # Support a location object returned directly by the extractor.
    if not summary and isinstance(location_summary, str):
        summary = {
            "primary_location": location_summary,
        }

    return {
        "primary_location": (
            summary.get("primary_location")
            or summary.get("location")
            or summary.get("formatted_address")
        ),
        "locations": safe_list(locations),
        "total": len(safe_list(locations)),
        "country": summary.get("country"),
        "city": summary.get("city"),
        "region": summary.get("region"),
        "postal_code": summary.get("postal_code"),
        "detection_status": summary.get(
            "detection_status",
            "completed" if locations or summary else "not_detected",
        ),
    }


def build_business_summary_section(data: dict) -> dict:
    """Build generated business summary information."""

    business = safe_dict(data.get("business"))

    summary = (
        data.get("business_summary")
        or business.get("description")
    )

    return {
        "summary": safe_string(summary),
        "source": (
            "generated_or_extracted"
            if summary
            else "not_available"
        ),
    }


def build_website_section(data: dict) -> dict:
    """Build website crawl information."""

    website = safe_dict(data.get("website"))

    # Support both nested and original crawler output.
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
            intent.get("score", 0),
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

        "phone_intelligence": build_phone_section(data),

        "mx_validation": build_mx_section(data),

        "technology_intelligence": (
            build_technology_section(data)
        ),

        "hiring_intelligence": (
            build_hiring_section(data)
        ),

        "business_intelligence": {
            "industry": build_industry_section(data),
            "location": build_location_section(data),
            "summary": build_business_summary_section(data),
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
