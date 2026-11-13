
"""
B2B Domain Sniper
Centralized runtime configuration.
"""

from dataclasses import dataclass

from .models import ActorInput


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Immutable settings used throughout the application."""

    max_pages_per_domain: int = 6
    max_concurrency: int = 20

    extract_emails: bool = True
    extract_phones: bool = True
    detect_technologies: bool = True
    detect_hiring_signals: bool = True
    generate_business_summary: bool = True
    calculate_intent_score: bool = True

    request_timeout_seconds: float = 20.0
    max_retries: int = 2
    max_redirects: int = 5
    max_response_bytes: int = 2 * 1024 * 1024

    user_agent: str = (
        "B2B-Domain-Sniper/0.1 "
        "(public business website research)"
    )


def load_config(actor_input: ActorInput) -> RuntimeConfig:
    """
    Convert validated Actor input into immutable runtime settings.
    """

    return RuntimeConfig(
        max_pages_per_domain=actor_input.max_pages_per_domain,
        max_concurrency=actor_input.max_concurrency,
        extract_emails=actor_input.extract_emails,
        extract_phones=actor_input.extract_phones,
        detect_technologies=actor_input.detect_technologies,
        detect_hiring_signals=actor_input.detect_hiring_signals,
        generate_business_summary=actor_input.generate_business_summary,
        calculate_intent_score=actor_input.calculate_intent_score,
    )
  
