
"""
B2B Domain Sniper
Main application orchestrator.

Responsibilities:
- Initialize the Apify Actor.
- Read and validate input.
- Load runtime configuration.
- Process domains concurrently.
- Build structured results.
- Send successful results through the billing layer.
"""

import asyncio
from typing import Any

from apify import Actor

from .config import load_config
from .models import validate_input
from .crawler import process_domain
from .result_builder import build_result
from .billing import charge_and_push_result


async def process_single_domain(
    domain: str,
    config: Any,
    semaphore: asyncio.Semaphore,
) -> bool:
    """
    Process one company domain.

    Returns:
        True if the result was successfully processed and submitted.
        False if processing failed.
    """

    async with semaphore:
        try:
            Actor.log.info("Processing domain: %s", domain)

            # Crawl and analyze the company domain.
            domain_data = await process_domain(domain, config)

            # Convert collected information into the standard output.
            result = build_result(domain, domain_data, config)

            # Handle billing and Dataset submission in one layer.
            await charge_and_push_result(result)

            Actor.log.info("Successfully processed: %s", domain)
            return True

        except Exception as exc:
            # One domain failure must not stop the remaining domains.
            Actor.log.error(
                "Failed to process %s: %s",
                domain,
                str(exc),
            )
            return False


async def run_application() -> None:
    """Run the complete B2B Domain Sniper workflow."""

    raw_input = await Actor.get_input()

    if not raw_input:
        raise ValueError("Actor input is empty or missing.")

    # Validate and normalize user input.
    validated_input = validate_input(raw_input)

    # Load application settings.
    config = load_config(validated_input)

    domains = validated_input.domains

    if not domains:
        raise ValueError("At least one company domain is required.")

    Actor.log.info(
        "Starting B2B Domain Sniper with %s domains.",
        len(domains),
    )

    semaphore = asyncio.Semaphore(config.max_concurrency)

    # Process domains concurrently while respecting the configured limit.
    tasks = [
        process_single_domain(domain, config, semaphore)
        for domain in domains
    ]

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    successful = sum(result is True for result in results)
    failed = len(domains) - successful

    Actor.log.info(
        "Run completed. Successful: %s | Failed: %s | Total: %s",
        successful,
        failed,
        len(domains),
    )


async def main() -> None:
    """Apify Actor lifecycle entry point."""

    async with Actor:
        Actor.log.info("B2B Domain Sniper Actor started.")

        try:
            await run_application()

        except Exception as exc:
            Actor.log.error(
                "Actor execution failed: %s",
                str(exc),
            )
            raise

        finally:
            Actor.log.info("B2B Domain Sniper Actor stopped.")


if __name__ == "__main__":
    asyncio.run(main())
                           
