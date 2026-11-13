"""
b2b-domain-sniper
File: src/billing.py

Usage and Billing Management Engine.

Features:
- API usage tracking
- Domain scan accounting
- Page crawl accounting
- Email processing accounting
- Credit calculation
- Usage limits
- Estimated cost calculation
- Billing summary
- Apify integration metadata
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any


DEFAULT_PRICING = {
    "domain_scan": 1.0,
    "page_crawl": 0.1,
    "email_processed": 0.05,
    "technology_detection": 0.2,
    "hiring_analysis": 0.2,
}


DEFAULT_LIMITS = {
    "domains": 100,
    "pages": 1000,
    "emails": 5000,
}


@dataclass
class UsageRecord:
    """Store usage statistics for one execution."""

    domains_scanned: int = 0
    pages_crawled: int = 0
    emails_processed: int = 0
    technology_scans: int = 0
    hiring_scans: int = 0

    total_credits: float = 0.0

    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


class BillingManager:
    """
    Manage usage and estimated billing.

    Pricing units are configurable.
    Currency and actual payment processing are external.
    """

    def __init__(
        self,
        pricing: dict[str, float] | None = None,
        limits: dict[str, int] | None = None,
    ) -> None:

        self.pricing = dict(
            DEFAULT_PRICING
        )

        if pricing:
            self.pricing.update(pricing)

        self.limits = dict(
            DEFAULT_LIMITS
        )

        if limits:
            self.limits.update(limits)

        self.usage = UsageRecord()

        self._lock = RLock()

        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """Validate pricing and usage limit configuration."""

        for key, value in self.pricing.items():

            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
            ):
                raise ValueError(
                    f"Invalid pricing value: {key}"
                )

        for key, value in self.limits.items():

            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(
                    f"Invalid usage limit: {key}"
                )

    @staticmethod
    def _validate_amount(
        value: int,
        name: str,
    ) -> None:

        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            raise ValueError(
                f"{name} must be a non-negative integer"
            )

    def check_limits(
        self,
        domains: int = 0,
        pages: int = 0,
        emails: int = 0,
    ) -> dict[str, Any]:
        """Check whether requested usage fits configured limits."""

        self._validate_amount(domains, "domains")
        self._validate_amount(pages, "pages")
        self._validate_amount(emails, "emails")

        requested = {
            "domains": domains,
            "pages": pages,
            "emails": emails,
        }

        with self._lock:

            current = {
                "domains": self.usage.domains_scanned,
                "pages": self.usage.pages_crawled,
                "emails": self.usage.emails_processed,
            }

            exceeded = []

            for key, amount in requested.items():

                limit = self.limits[key]

                if current[key] + amount > limit:
                    exceeded.append({
                        "resource": key,
                        "current": current[key],
                        "requested": amount,
                        "limit": limit,
                    })

        return {
            "allowed": not bool(exceeded),
            "exceeded": exceeded,
        }

    def record_usage(
        self,
        domains: int = 0,
        pages: int = 0,
        emails: int = 0,
        technology_scans: int = 0,
        hiring_scans: int = 0,
    ) -> dict[str, Any]:
        """Record resource usage and calculate consumed credits."""

        values = {
            "domains": domains,
            "pages": pages,
            "emails": emails,
            "technology_scans": technology_scans,
            "hiring_scans": hiring_scans,
        }

        for key, value in values.items():
            self._validate_amount(value, key)

        limit_check = self.check_limits(
            domains=domains,
            pages=pages,
            emails=emails,
        )

        if not limit_check["allowed"]:
            return {
                "success": False,
                "status": "usage_limit_exceeded",
                "limit_check": limit_check,
            }

        credits = (
            domains * self.pricing["domain_scan"]
            + pages * self.pricing["page_crawl"]
            + emails * self.pricing["email_processed"]
            + technology_scans * self.pricing["technology_detection"]
            + hiring_scans * self.pricing["hiring_analysis"]
        )

        with self._lock:

            self.usage.domains_scanned += domains
            self.usage.pages_crawled += pages
            self.usage.emails_processed += emails

            self.usage.technology_scans += technology_scans
            self.usage.hiring_scans += hiring_scans

            self.usage.total_credits += credits

            total = round(
                self.usage.total_credits,
                4,
            )

        return {
            "success": True,
            "status": "usage_recorded",
            "credits_consumed": round(credits, 4),
            "total_credits": total,
        }

    def calculate_cost(
        self,
        usage: dict[str, int],
    ) -> dict[str, Any]:
        """Calculate estimated cost for supplied usage."""

        mapping = {
            "domains": "domain_scan",
            "pages": "page_crawl",
            "emails": "email_processed",
            "technology_scans": "technology_detection",
            "hiring_scans": "hiring_analysis",
        }

        breakdown = {}
        total = 0.0

        for resource, pricing_key in mapping.items():

            quantity = usage.get(resource, 0)

            self._validate_amount(
                quantity,
                resource,
            )

            unit_price = self.pricing[pricing_key]

            amount = quantity * unit_price

            breakdown[resource] = {
                "quantity": quantity,
                "unit_price": unit_price,
                "total": round(amount, 4),
            }

            total += amount

        return {
            "breakdown": breakdown,
            "estimated_total": round(total, 4),
            "currency": "credits",
            "is_actual_charge": False,
        }

    def get_usage_summary(self) -> dict[str, Any]:
        """Return current usage and billing information."""

        with self._lock:

            usage = {
                "domains_scanned": self.usage.domains_scanned,
                "pages_crawled": self.usage.pages_crawled,
                "emails_processed": self.usage.emails_processed,
                "technology_scans": self.usage.technology_scans,
                "hiring_scans": self.usage.hiring_scans,
            }

            total_credits = self.usage.total_credits

            created_at = self.usage.created_at

        return {
            "usage": usage,
            "limits": dict(self.limits),
            "pricing": dict(self.pricing),
            "total_credits": round(total_credits, 4),
            "created_at": created_at,
        }

    def reset_usage(self) -> None:
        """Reset usage statistics for a new accounting period."""

        with self._lock:
            self.usage = UsageRecord()

    def to_apify_metadata(self) -> dict[str, Any]:
        """Generate usage metadata for an Apify integration."""

        summary = self.get_usage_summary()

        return {
            "actor": "b2b-domain-sniper",
            "usage": summary["usage"],
            "credits_consumed": summary["total_credits"],
            "recorded_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "billing_status": "usage_calculated",
            "payment_status": "not_processed",
        }


def create_billing_manager(
    pricing: dict[str, float] | None = None,
    limits: dict[str, int] | None = None,
) -> BillingManager:
    """Create a configured billing manager."""

    return BillingManager(
        pricing=pricing,
        limits=limits,
    )
