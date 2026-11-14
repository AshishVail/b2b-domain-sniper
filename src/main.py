"""
B2B Domain Sniper
Main application orchestrator.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from apify import Actor

from .config import load_config
from .models import validate_input
from .crawler import process_domain
from .email_extractor import extract_from_pages as extract_emails_from_pages
from .phone_extractor import extract_from_pages as extract_phones_from_pages
from .industry_detector import detect_industry_from_pages
from .location_extractor import (
    extract_from_pages as extract_locations_from_pages,
    build_location_summary,
)
from .business_summary import generate_business_summary
from .technology_detector import detect_from_pages as detect_technology_from_pages
from .hiring_detector import detect_hiring_from_pages
from .mx_validator import validate_mx
from .intent_scorer import calculate_intent
from .result_builder import build_result


def _disabled_technology_result() -> dict:
    return {
        "technologies": [],
        "technology_count": 0,
        "categories": {},
        "detection_status": "disabled",
    }


def _disabled_hiring_result() -> dict:
    return {
        "hiring_detected": False,
        "hiring_score": 0,
        "hiring_status": "disabled",
        "matched_keywords": [],
        "career_links": [],
        "job_board_links": [],
    }


def _get_primary_phone(phone_numbers: list) -> str | None:
    """Return the first extracted phone number, if available."""

    for item in phone_numbers:
        if isinstance(item, dict) and item.get("phone"):
            return item["phone"]

        if isinstance(item, str) and item.strip():
            return item.strip()

    return None


def _get_primary_industry(industry_data: Any) -> str | None:
    """Read the primary industry from the detector result."""

    if not isinstance(industry_data, dict):
        return None

    return (
        industry_data.get("primary_industry")
        or industry_data.get("industry")
    )


async def process_single_domain(
    domain: str,
    config: Any,
    semaphore: asyncio.Semaphore,
) -> bool:

    async with semaphore:
        try:
            Actor.log.info("Processing: %s", domain)

            # 1. Crawl website.
            domain_data = await process_domain(
                domain,
                config,
            )

            pages = domain_data.get("pages", []) or []
            hostname = domain_data.get("domain") or domain

            # 2. Extract emails.
            emails = []

            if getattr(config, "extract_emails", True):
                try:
                    emails = extract_emails_from_pages(pages) or []
                except Exception as exc:
                    Actor.log.warning(
                        "Email extraction failed for %s: %s",
                        domain,
                        str(exc),
                    )

            # 3. Extract phone numbers.
            phone_numbers = []

            if getattr(config, "extract_phones", True):
                try:
                    phone_numbers = extract_phones_from_pages(
                        pages,
                        max_results=200,
                    ) or []
                except Exception as exc:
                    Actor.log.warning(
                        "Phone extraction failed for %s: %s",
                        domain,
                        str(exc),
                    )

            # 4. Detect industry.
            industry_data = {
                "primary_industry": None,
                "confidence": 0,
                "candidates": [],
                "matched_keywords": [],
                "detection_status": "not_detected",
            }

            try:
                industry_data = detect_industry_from_pages(
                    pages
                ) or industry_data
            except Exception as exc:
                Actor.log.warning(
                    "Industry detection failed for %s: %s",
                    domain,
                    str(exc),
                )

            # 5. Extract business location.
            locations = []
            location_data = {}

            try:
                locations = extract_locations_from_pages(
                    pages,
                    max_results=50,
                ) or []

                location_data = build_location_summary(
                    locations
                ) or {}

            except Exception as exc:
                Actor.log.warning(
                    "Location extraction failed for %s: %s",
                    domain,
                    str(exc),
                )

            # 6. Detect technologies.
            if getattr(config, "detect_technologies", True):
                try:
                    technology = detect_technology_from_pages(
                        pages
                    ) or _disabled_technology_result()
                except Exception as exc:
                    Actor.log.warning(
                        "Technology detection failed for %s: %s",
                        domain,
                        str(exc),
                    )
                    technology = _disabled_technology_result()
                    technology["detection_status"] = "error"
            else:
                technology = _disabled_technology_result()

            # 7. Detect hiring signals.
            if getattr(config, "detect_hiring_signals", True):
                try:
                    hiring = detect_hiring_from_pages(
                        pages
                    ) or _disabled_hiring_result()
                except Exception as exc:
                    Actor.log.warning(
                        "Hiring detection failed for %s: %s",
                        domain,
                        str(exc),
                    )
                    hiring = _disabled_hiring_result()
                    hiring["hiring_status"] = "error"
            else:
                hiring = _disabled_hiring_result()

            # 8. Validate MX records.
            try:
                mx_validation = await validate_mx(hostname)

            except Exception as exc:
                Actor.log.warning(
                    "MX validation failed for %s: %s",
                    domain,
                    str(exc),
                )

                mx_validation = {
                    "domain": hostname,
                    "valid": False,
                    "mail_configured": None,
                    "status": "dns_lookup_error",
                    "error": str(exc),
                }

            # 9. Website information.
            homepage = pages[0] if pages else {}

            website_url = domain_data.get(
                "website_url",
                domain,
            )

            homepage_status = homepage.get("status_code")

            homepage_reachable = bool(
                homepage.get("html")
                and isinstance(homepage_status, int)
                and 200 <= homepage_status < 400
            )

            website = {
                "url": website_url,
                "reachable": homepage_reachable,
                "status_code": homepage_status,
                "pages_analyzed": len(pages),
                "pages": pages,
            }

            # 10. Generate business description.
            # Prefer an actual meta description. Do not label arbitrary
            # homepage text as a verified business description.
            existing_description = homepage.get("description") or None

            business_description = existing_description

            if getattr(config, "generate_business_summary", True):
                try:
                    generated_summary = generate_business_summary(
                        pages,
                        existing_description=existing_description,
                        max_length=500,
                    )

                    if generated_summary:
                        business_description = generated_summary

                except Exception as exc:
                    Actor.log.warning(
                        "Business summary generation failed for %s: %s",
                        domain,
                        str(exc),
                    )

            # 11. Basic business information.
            metadata = homepage.get("metadata") or {}

            if not isinstance(metadata, dict):
                metadata = {}

            business_name = (
                metadata.get("og:site_name")
                or metadata.get("application-name")
                or homepage.get("title")
                or hostname
            )

            business = {
                "name": business_name,
                "domain": hostname,
                "website": website_url,
                "description": business_description,
                "industry": _get_primary_industry(industry_data),
                "industry_details": industry_data,
                "location": location_data,
                "phone": _get_primary_phone(phone_numbers),
                "phone_numbers": phone_numbers,
            }

            # 12. Unified result data.
            crawl_errors = list(
                domain_data.get("errors", []) or []
            )

            result_data = {
                "domain": hostname,
                "scan_id": str(uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": (
                    "failed" if not homepage_reachable
                    else "partial" if crawl_errors
                    else "completed"
                ),
                "business": business,
                "website": website,
                "emails": emails,
                "phone_numbers": phone_numbers,
                "industry": industry_data,
                "locations": locations,
                "location": location_data,
                "business_summary": business_description,
                "mx_validation": mx_validation,
                "technology": technology,
                "hiring": hiring,
                "errors": crawl_errors,
            }

            # 13. Calculate intent score.
            if getattr(config, "calculate_intent_score", True):
                intent_data = dict(result_data)

                # Intent scorer expects email strings.
                intent_data["emails"] = [
                    item["email"]
                    for item in emails
                    if isinstance(item, dict)
                    and item.get("email")
                ]

                try:
                    result_data["intent"] = calculate_intent(
                        intent_data
                    )

                    result_data["intent"]["method"] = "heuristic"
                    result_data["intent"][
                        "not_a_purchase_prediction"
                    ] = True

                except Exception as exc:
                    Actor.log.warning(
                        "Intent scoring failed for %s: %s",
                        domain,
                        str(exc),
                    )

                    result_data["intent"] = {
                        "score": 0,
                        "status": "error",
                        "error": str(exc),
                    }

            # 14. Build final JSON.
            result = build_result(
                domain,
                result_data,
                config,
            )

            # 15. Save to Apify Dataset.
            await Actor.push_data(result)

            Actor.log.info(
                (
                    "Completed: %s | Pages: %d | Emails: %d | "
                    "Phones: %d | Industry: %s | Technologies: %d | "
                    "Hiring: %s"
                ),
                domain,
                len(pages),
                len(emails),
                len(phone_numbers),
                business.get("industry") or "Not detected",
                technology.get("technology_count", 0),
                hiring.get("hiring_detected", False),
            )

            return True

        except Exception:
            Actor.log.exception(
                "Processing failed: %s",
                domain,
            )
            return False


async def run_application() -> None:

    raw_input = await Actor.get_input()

    if not raw_input:
        raise ValueError(
            "Actor input is empty or missing."
        )

    validated_input = validate_input(raw_input)
    config = load_config(validated_input)
    domains = validated_input.domains

    if not domains:
        raise ValueError(
            "At least one domain is required."
        )

    Actor.log.info(
        "Starting B2B Domain Sniper | Domains: %d",
        len(domains),
    )

    semaphore = asyncio.Semaphore(
        max(1, getattr(config, "max_concurrency", 5))
    )

    tasks = [
        process_single_domain(
            domain,
            config,
            semaphore,
        )
        for domain in domains
    ]

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    successful = sum(
        result is True for result in results
    )

    failed = len(domains) - successful

    Actor.log.info(
        "Run completed | Successful: %d | Failed: %d | Total: %d",
        successful,
        failed,
        len(domains),
    )


async def main() -> None:

    async with Actor:

        Actor.log.info(
            "B2B Domain Sniper Actor started."
        )

        try:
            await run_application()

        except Exception:
            Actor.log.exception(
                "Actor execution failed."
            )
            raise

        finally:
            Actor.log.info(
                "B2B Domain Sniper Actor stopped."
            )


if __name__ == "__main__":
    asyncio.run(main())
