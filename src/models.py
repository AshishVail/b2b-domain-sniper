
"""
B2B Domain Sniper
Input validation and shared data models.
"""

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class ActorInput(BaseModel):
    """Validated input received from Apify."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )

    domains: list[str] = Field(
        min_length=1,
        max_length=500,
        description="Company domains or website URLs.",
    )

    max_pages_per_domain: int = Field(
        default=6,
        ge=1,
        le=8,
    )

    max_concurrency: int = Field(
        default=20,
        ge=1,
        le=50,
    )

    extract_emails: bool = True
    extract_phones: bool = True
    detect_technologies: bool = True
    detect_hiring_signals: bool = True
    generate_business_summary: bool = True
    calculate_intent_score: bool = True

    @field_validator("domains")
    @classmethod
    def normalize_domains(cls, values: list[str]) -> list[str]:
        """Normalize URLs and remove duplicate entries."""

        normalized: list[str] = []
        seen: set[str] = set()

        for raw_value in values:
            value = raw_value.strip()

            if not value:
                raise ValueError("Domain entries cannot be empty.")

            if "://" not in value:
                value = f"https://{value}"

            try:
                parsed = urlsplit(value)
                hostname = parsed.hostname
                scheme = parsed.scheme.lower()

                if scheme not in {"http", "https"}:
                    raise ValueError("Only HTTP and HTTPS URLs are allowed.")

                if not hostname:
                    raise ValueError("A valid hostname is required.")

                if parsed.username or parsed.password:
                    raise ValueError("URLs containing credentials are not allowed.")

                if parsed.port and not 1 <= parsed.port <= 65535:
                    raise ValueError("Invalid URL port.")

                hostname = hostname.encode("idna").decode("ascii").lower()

                if hostname.endswith("."):
                    hostname = hostname[:-1]

                if not hostname or "." not in hostname:
                    raise ValueError("Enter a valid public company domain.")

                if any(char.isspace() for char in hostname):
                    raise ValueError("Hostname cannot contain whitespace.")

                netloc = hostname

                if parsed.port:
                    netloc = f"{hostname}:{parsed.port}"

                normalized_url = urlunsplit(
                    (
                        scheme,
                        netloc,
                        parsed.path or "/",
                        parsed.query,
                        "",
                    )
                )

            except (ValueError, UnicodeError) as exc:
                raise ValueError(
                    f"Invalid domain entry '{raw_value}': {exc}"
                ) from exc

            if normalized_url not in seen:
                seen.add(normalized_url)
                normalized.append(normalized_url)

        if not normalized:
            raise ValueError("At least one valid domain is required.")

        return normalized


def validate_input(raw_input: dict[str, Any]) -> ActorInput:
    """Validate raw Apify input and return a typed model."""

    if not isinstance(raw_input, dict):
        raise ValueError("Actor input must be a JSON object.")

    return ActorInput.model_validate(raw_input)
