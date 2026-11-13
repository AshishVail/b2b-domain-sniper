
"""
B2B Domain Sniper
Main application orchestrator.
"""

import asyncio
from typing import Any

from apify import Actor

from .config import load_config
from .models import validate_input
from .crawler import process_domain
from .email_extractor import extract_from_pages
from .technology_detector import detect_from_pages
from .hiring_detector import detect_hiring_from_pages
from .mx_validator import validate_mx
from .intent_scorer import calculate_intent
from .result_builder import build_result


async def process_single_domain(
    domain: str,
    config: Any,
    semaphore: asyncio.Semaphore,
) -> bool:

    async with semaphore:
        try:
            Actor.log.info("Processing: %s", domain)

            # 1. Crawl website
            domain_data = await process_domain(
                domain,
                config,
            )

            pages = domain_data.get("pages", [])
            hostname = domain_data.get("domain")

            # 2. Extract emails
            emails = []

            if config.extract_emails:
                emails = extract_from_pages(pages)

            # 3. Detect technologies
            technology = detect_from_pages(
                pages
            ) if config.detect_technologies else {
                "technologies": [],
                "technology_count": 0,
                "categories": {},
                "detection_status": "disabled",
            }

            # 4. Detect hiring signals
            hiring = detect_hiring_from_pages(
                pages
            ) if config.detect_hiring_signals else {
                "hiring_detected": False,
                "hiring_score": 0,
                "hiring_status": "disabled",
                "matched_keywords": [],
                "career_links": [],
                "job_board_links": [],
            }

            # 5. Validate MX records
            try:
                mx_validation = await validate_mx(
                    hostname
                )
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

            # 6. Website information
            homepage = pages[0] if pages else {}

            website = {
                "url": domain_data.get(
                    "website_url", domain
                ),
                "reachable": bool(homepage.get("html")),
                "status_code": homepage.get("status_code"),
                "pages_analyzed": len(pages),
                "pages": pages,
            }

            # 7. Basic business information
            business = {
                "name": homepage.get("title") or hostname,
                "domain": hostname,
                "website": domain_data.get(
                    "website_url", domain
                ),
                "description": (
                    homepage.get("description")
                    or homepage.get("text", "")[:500]
                    or None
                ),
                "industry": None,
                "location": None,
                "phone": None,
            }

            # 8. Unified result data
            result_data = {
                "domain": hostname,
                "status": (
                    "completed" if pages else "failed"
                ),
                "business": business,
                "website": website,
                "emails": emails,
                "mx_validation": mx_validation,
                "technology": technology,
                "hiring": hiring,
                "errors": domain_data.get("errors", []),
            }

            # 9. Calculate intent score
            if config.calculate_intent_score:
                intent_data = dict(result_data)

                # Intent scorer expects email strings
                intent_data["emails"] = [
                    item["email"]
                    for item in emails
                    if isinstance(item, dict)
                    and item.get("email")
                ]

                result_data["intent"] = calculate_intent(
                    intent_data
                )

            # 10. Build final JSON
            result = build_result(
                domain,
                result_data,
                config,
            )

            # 11. Save to Apify Dataset
            await Actor.push_data(result)

            Actor.log.info(
                "Completed: %s | Pages: %d | Emails: %d | Technologies: %d | Hiring: %s",
                domain,
                len(pages),
                len(emails),
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
        config.max_concurrency
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
