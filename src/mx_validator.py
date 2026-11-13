
"""
b2b-domain-sniper
File: src/mx_validator.py

Professional DNS and MX validation module.

Features:
- MX record lookup
- A and AAAA fallback
- Email domain validation
- Async DNS-over-HTTPS requests
- Batch domain validation
- Concurrency control
- Timeout and error handling
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx


DNS_ENDPOINT = "https://cloudflare-dns.com/dns-query"

DEFAULT_TIMEOUT = 8.0
DEFAULT_CONCURRENCY = 10
MAX_CONCURRENCY = 50

DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)"
    r"(?:[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,63}$"
)


def normalize_domain(domain: str) -> str:
    """Normalize and validate a domain name."""

    if not isinstance(domain, str):
        raise ValueError("Domain must be a string")

    domain = domain.strip().lower().rstrip(".")

    if "@" in domain:
        domain = domain.rsplit("@", 1)[1]

    if not DOMAIN_PATTERN.fullmatch(domain):
        raise ValueError(f"Invalid domain: {domain}")

    return domain


def extract_email_domain(email: str) -> str:
    """Extract domain from an email address."""

    if not isinstance(email, str):
        raise ValueError("Email must be a string")

    email = email.strip()

    if email.count("@") != 1:
        raise ValueError("Invalid email address")

    local, domain = email.rsplit("@", 1)

    if not local:
        raise ValueError("Email local part is empty")

    return normalize_domain(domain)


async def dns_query(
    client: httpx.AsyncClient,
    domain: str,
    record_type: str,
) -> dict[str, Any]:
    """Perform a DNS-over-HTTPS query."""

    response = await client.get(
        DNS_ENDPOINT,
        params={
            "name": domain,
            "type": record_type,
        },
        headers={
            "accept": "application/dns-json"
        },
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict):
        raise ValueError("Invalid DNS response")

    return data


async def get_dns_records(
    client: httpx.AsyncClient,
    domain: str,
    record_type: str,
) -> list[dict[str, Any]]:
    """Retrieve DNS records of a specific type."""

    try:
        data = await dns_query(
            client,
            domain,
            record_type,
        )

        return [
            {
                "name": record.get("name"),
                "type": record.get("type"),
                "ttl": record.get("TTL"),
                "value": record.get("data"),
            }
            for record in data.get("Answer", [])
            if record.get("data")
        ]

    except (
        httpx.HTTPError,
        ValueError,
        TypeError,
        asyncio.TimeoutError,
    ):
        return []


async def validate_mx(
    domain: str,
    client: httpx.AsyncClient | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    Validate domain mail routing configuration.

    MX records are preferred.

    If MX records are missing, A/AAAA records are
    checked as implicit mail-routing fallback indicators.

    This does not verify individual email inboxes.
    """

    domain = normalize_domain(domain)

    owns_client = client is None

    if owns_client:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
            headers={
                "User-Agent": "b2b-domain-sniper/1.0",
                "Accept": "application/dns-json",
            },
        )

    assert client is not None

    try:
        mx_records = await get_dns_records(
            client,
            domain,
            "MX",
        )

        if mx_records:
            return {
                "domain": domain,
                "valid": True,
                "mail_configured": True,
                "status": "valid_mx",
                "mx_records": mx_records,
                "fallback_records": [],
                "mailbox_verified": False,
            }

        a_records, aaaa_records = await asyncio.gather(
            get_dns_records(client, domain, "A"),
            get_dns_records(client, domain, "AAAA"),
        )

        fallback_records = a_records + aaaa_records

        if fallback_records:
            return {
                "domain": domain,
                "valid": True,
                "mail_configured": True,
                "status": "implicit_mx_fallback",
                "mx_records": [],
                "fallback_records": fallback_records,
                "mailbox_verified": False,
            }

        return {
            "domain": domain,
            "valid": False,
            "mail_configured": False,
            "status": "no_mail_routing_records",
            "mx_records": [],
            "fallback_records": [],
            "mailbox_verified": False,
        }

    except (
        httpx.HTTPError,
        asyncio.TimeoutError,
    ) as exc:
        return {
            "domain": domain,
            "valid": False,
            "mail_configured": None,
            "status": "dns_lookup_error",
            "mx_records": [],
            "fallback_records": [],
            "mailbox_verified": False,
            "error": str(exc),
        }

    finally:
        if owns_client:
            await client.aclose()


async def validate_email_domain(
    email: str,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Validate the mail configuration of an email domain."""

    domain = extract_email_domain(email)

    result = await validate_mx(
        domain,
        client=client,
    )

    return {
        "email": email.strip(),
        **result,
    }


async def validate_domains(
    domains: list[str],
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[dict[str, Any]]:
    """Validate multiple domains asynchronously."""

    concurrency = max(
        1,
        min(concurrency, MAX_CONCURRENCY),
    )

    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(DEFAULT_TIMEOUT),
        follow_redirects=False,
        headers={
            "User-Agent": "b2b-domain-sniper/1.0",
            "Accept": "application/dns-json",
        },
    ) as client:

        async def worker(
            domain: str,
        ) -> dict[str, Any]:

            async with semaphore:
                try:
                    return await validate_mx(
                        domain,
                        client=client,
                    )

                except ValueError as exc:
                    return {
                        "domain": domain,
                        "valid": False,
                        "mail_configured": None,
                        "status": "invalid_domain",
                        "error": str(exc),
                    }

        return await asyncio.gather(
            *[
                worker(domain)
                for domain in domains
            ]
        )


async def validate_emails(
    emails: list[str],
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[dict[str, Any]]:
    """Validate multiple email domains asynchronously."""

    concurrency = max(
        1,
        min(concurrency, MAX_CONCURRENCY),
    )

    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(DEFAULT_TIMEOUT),
        follow_redirects=False,
        headers={
            "User-Agent": "b2b-domain-sniper/1.0",
            "Accept": "application/dns-json",
        },
    ) as client:

        async def worker(
            email: str,
        ) -> dict[str, Any]:

            async with semaphore:
                try:
                    return await validate_email_domain(
                        email,
                        client=client,
                    )

                except ValueError as exc:
                    return {
                        "email": email,
                        "valid": False,
                        "mail_configured": None,
                        "status": "invalid_email",
                        "error": str(exc),
                    }

        return await asyncio.gather(
            *[
                worker(email)
                for email in emails
            ]
        )
