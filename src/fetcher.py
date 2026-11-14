
"""
B2B Domain Sniper
Secure asynchronous website fetcher.

Features:
- HTTP/HTTPS URL validation
- Public IP and DNS validation
- Redirect validation
- Retry with exponential backoff
- Retry-After support
- Response size protection
- HTML content extraction
- Async connection pooling
- Consistent result structure
"""

import asyncio
import ipaddress
import socket

from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from .config import RuntimeConfig


RETRYABLE_STATUS_CODES = {
    408,
    425,
    429,
    500,
    502,
    503,
    504,
}

REDIRECT_STATUS_CODES = {
    301,
    302,
    303,
    307,
    308,
}

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata",
    "metadata.google.internal",
}


# --------------------------------------------------
# Configuration helpers
# --------------------------------------------------

def _config_value(
    config: RuntimeConfig,
    name: str,
    default: Any,
) -> Any:
    """Read a configuration value with a fallback."""

    return getattr(config, name, default)


# --------------------------------------------------
# IP and URL security
# --------------------------------------------------

def _is_public_ip(address: str) -> bool:
    """Check whether an IP address is globally routable."""

    try:
        ip = ipaddress.ip_address(address)

        if isinstance(ip, ipaddress.IPv6Address):
            if ip.ipv4_mapped is not None:
                return ip.ipv4_mapped.is_global

        return ip.is_global

    except ValueError:
        return False


async def validate_public_http_url(url: str) -> None:
    """
    Validate HTTP/HTTPS URLs.

    Reject:
    - Localhost destinations
    - Private IP addresses
    - Loopback addresses
    - Link-local addresses
    - Reserved IP addresses
    - Non-public DNS destinations
    - Metadata endpoints
    - URL credentials
    """

    if not isinstance(url, str) or not url:
        raise ValueError("Invalid URL.")

    if url != url.strip():
        raise ValueError("URL contains surrounding whitespace.")

    try:
        parsed = urlsplit(url)

    except ValueError as exc:
        raise ValueError("Malformed URL.") from exc

    scheme = parsed.scheme.lower()

    if scheme not in {"http", "https"}:
        raise ValueError(
            "Only HTTP and HTTPS URLs are allowed."
        )

    if parsed.username or parsed.password:
        raise ValueError(
            "URL credentials are not allowed."
        )

    try:
        hostname = parsed.hostname

        port = parsed.port

    except ValueError as exc:
        raise ValueError(
            "Invalid URL hostname or port."
        ) from exc

    if not hostname:
        raise ValueError(
            "URL hostname is missing."
        )

    hostname = hostname.rstrip(".").lower()

    if not hostname:
        raise ValueError(
            "Invalid hostname."
        )

    if (
        hostname in BLOCKED_HOSTNAMES
        or hostname.endswith(".localhost")
        or hostname.endswith(".local")
    ):
        raise ValueError(
            "Local or metadata hostnames are blocked."
        )

    # Validate literal IP addresses first.

    try:
        literal_ip = ipaddress.ip_address(hostname)

    except ValueError:
        literal_ip = None

    if literal_ip is not None:

        if not _is_public_ip(hostname):
            raise ValueError(
                "Non-public IP destinations are blocked."
            )

        return

    # Normalize internationalized domain names.

    try:
        hostname = hostname.encode(
            "idna"
        ).decode("ascii")

    except UnicodeError as exc:
        raise ValueError(
            "Invalid internationalized hostname."
        ) from exc

    if not hostname or len(hostname) > 253:
        raise ValueError(
            "Invalid hostname length."
        )

    effective_port = port or (
        443 if scheme == "https" else 80
    )

    # Resolve DNS without blocking the event loop.

    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            effective_port,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )

    except socket.gaierror as exc:
        raise ValueError(
            f"DNS resolution failed for {hostname}."
        ) from exc

    except OSError as exc:
        raise ValueError(
            f"Unable to resolve {hostname}."
        ) from exc

    addresses = {
        record[4][0]
        for record in records
    }

    if not addresses:
        raise ValueError(
            f"No IP addresses found for {hostname}."
        )

    # Reject the entire hostname if any resolved address
    # is not globally routable.

    for address in addresses:

        if not _is_public_ip(address):
            raise ValueError(
                f"Hostname {hostname} resolves to a non-public IP."
            )


# --------------------------------------------------
# Retry handling
# --------------------------------------------------

def _retry_delay(
    response: httpx.Response,
    attempt: int,
) -> float:
    """Calculate a bounded retry delay."""

    retry_after = response.headers.get(
        "Retry-After"
    )

    if retry_after:

        try:
            delay = float(retry_after)

            return min(
                max(delay, 0.0),
                5.0,
            )

        except ValueError:
            pass

        try:
            retry_date = parsedate_to_datetime(
                retry_after
            )

            if retry_date.tzinfo is None:
                retry_date = retry_date.replace(
                    tzinfo=timezone.utc
                )

            from datetime import datetime

            delay = (
                retry_date
                - datetime.now(timezone.utc)
            ).total_seconds()

            return min(
                max(delay, 0.0),
                5.0,
            )

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            pass

    return min(
        0.5 * (2 ** attempt),
        5.0,
    )


# --------------------------------------------------
# Response size protection
# --------------------------------------------------

async def _read_limited_response(
    response: httpx.Response,
    max_bytes: int,
) -> bytes:
    """
    Read response without exceeding the configured limit.

    Uses decoded response chunks, so the size limit
    also protects against compressed response expansion.
    """

    if max_bytes <= 0:
        raise ValueError(
            "Maximum response size must be positive."
        )

    content_length = response.headers.get(
        "Content-Length"
    )

    if content_length is not None:

        try:
            declared_size = int(content_length)

        except (ValueError, TypeError) as exc:
            raise ValueError(
                "Invalid Content-Length header."
            ) from exc

        if declared_size < 0:
            raise ValueError(
                "Invalid Content-Length header."
            )

        if declared_size > max_bytes:
            raise ValueError(
                "Response exceeds configured size limit."
            )

    chunks: list[bytes] = []
    total_size = 0

    async for chunk in response.aiter_bytes():

        if not chunk:
            continue

        total_size += len(chunk)

        if total_size > max_bytes:
            raise ValueError(
                "Response exceeds configured size limit."
            )

        chunks.append(chunk)

    return b"".join(chunks)


# --------------------------------------------------
# Standard page result
# --------------------------------------------------

def _page_result(
    url: str,
    status_code: int | None = None,
    html: str = "",
    content_type: str | None = None,
    headers: dict | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Create a consistent fetch result."""

    return {
        "url": url,
        "status_code": status_code,
        "html": html,
        "content_type": content_type,
        "headers": dict(headers or {}),
        "error": error,
    }


# --------------------------------------------------
# Main asynchronous fetcher
# --------------------------------------------------

async def fetch_page(
    client: httpx.AsyncClient,
    url: str,
    config: RuntimeConfig,
) -> dict[str, Any]:
    """
    Fetch one public website page safely.

    Handles:
    - DNS validation
    - Redirects
    - Temporary HTTP failures
    - Network retries
    - Response size limits
    - HTML decoding
    """

    current_url = url

    max_redirects = max(
        0,
        int(_config_value(config, "max_redirects", 5)),
    )

    max_retries = max(
        0,
        int(_config_value(config, "max_retries", 2)),
    )

    max_response_bytes = int(
        _config_value(
            config,
            "max_response_bytes",
            2 * 1024 * 1024,
        )
    )

    try:

        for redirect_number in range(
            max_redirects + 1
        ):

            # Validate every destination, including redirects.

            await validate_public_http_url(
                current_url
            )

            redirect_followed = False

            for attempt in range(
                max_retries + 1
            ):

                try:

                    async with client.stream(
                        "GET",
                        current_url,
                        follow_redirects=False,
                    ) as response:

                        status_code = response.status_code

                        headers = dict(
                            response.headers
                        )

                        # --------------------------
                        # Redirect handling
                        # --------------------------

                        if status_code in REDIRECT_STATUS_CODES:

                            location = response.headers.get(
                                "Location"
                            )

                            if not location:
                                return _page_result(
                                    current_url,
                                    status_code=status_code,
                                    headers=headers,
                                    error=(
                                        "Redirect without Location header."
                                    ),
                                )

                            if redirect_number >= max_redirects:
                                raise ValueError(
                                    "Maximum redirects exceeded."
                                )

                            next_url = urljoin(
                                current_url,
                                location,
                            )

                            # Validate the new URL on the next
                            # redirect iteration.

                            current_url = next_url

                            redirect_followed = True

                            break

                        # --------------------------
                        # Retry temporary HTTP errors
                        # --------------------------

                        if (
                            status_code in RETRYABLE_STATUS_CODES
                            and attempt < max_retries
                        ):

                            delay = _retry_delay(
                                response,
                                attempt,
                            )

                            await asyncio.sleep(
                                delay
                            )

                            continue

                        # --------------------------
                        # Content type detection
                        # --------------------------

                        content_type = response.headers.get(
                            "Content-Type",
                            "",
                        ).lower()

                        is_html = (
                            "text/html" in content_type
                            or "application/xhtml+xml" in content_type
                        )

                        # Ignore non-HTML content.

                        if not is_html:

                            return _page_result(
                                url=str(response.url),
                                status_code=status_code,
                                content_type=(
                                    content_type or None
                                ),
                                headers=headers,
                                error=(
                                    None
                                    if response.is_success
                                    else f"HTTP {status_code}"
                                ),
                            )

                        # --------------------------
                        # Read bounded response
                        # --------------------------

                        body = await _read_limited_response(
                            response,
                            max_response_bytes,
                        )

                        charset = (
                            response.encoding or "utf-8"
                        )

                        try:

                            html = body.decode(
                                charset,
                                errors="replace",
                            )

                        except LookupError:

                            html = body.decode(
                                "utf-8",
                                errors="replace",
                            )

                        # --------------------------
                        # Return result
                        # --------------------------

                        return _page_result(
                            url=str(response.url),
                            status_code=status_code,
                            html=(
                                html
                                if response.is_success
                                else ""
                            ),
                            content_type=content_type,
                            headers=headers,
                            error=(
                                None
                                if response.is_success
                                else f"HTTP {status_code}"
                            ),
                        )

                except (
                    httpx.TimeoutException,
                    httpx.TransportError,
                ):

                    if attempt >= max_retries:
                        raise

                    await asyncio.sleep(
                        min(
                            0.5 * (2 ** attempt),
                            5.0,
                        )
                    )

            # Follow the redirect after leaving the
            # previous response context.

            if redirect_followed:
                continue

            return _page_result(
                current_url,
                error="Request could not be completed.",
            )

        raise ValueError(
            "Unable to complete redirect chain."
        )

    except Exception as exc:

        return _page_result(
            url=current_url,
            error=str(exc),
        )


# --------------------------------------------------
# HTTP client factory
# --------------------------------------------------

def create_http_client(
    config: RuntimeConfig,
) -> httpx.AsyncClient:
    """
    Create reusable asynchronous HTTP client.

    The caller is responsible for closing the client
    using an async context manager.
    """

    timeout_seconds = float(
        _config_value(
            config,
            "request_timeout_seconds",
            20.0,
        )
    )

    if timeout_seconds <= 0:
        raise ValueError(
            "Request timeout must be positive."
        )

    max_concurrency = max(
        1,
        int(
            _config_value(
                config,
                "max_concurrency",
                20,
            )
        ),
    )

    user_agent = _config_value(
        config,
        "user_agent",
        "B2B-Domain-Sniper/1.0",
    )

    timeout = httpx.Timeout(
        timeout_seconds,
        connect=min(
            timeout_seconds,
            10.0,
        ),
    )

    limits = httpx.Limits(
        max_connections=max(
            10,
            max_concurrency * 3,
        ),
        max_keepalive_connections=max(
            5,
            max_concurrency,
        ),
        keepalive_expiry=15.0,
    )

    return httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        headers={
            "User-Agent": user_agent,
            "Accept": (
                "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"
            ),
            "Accept-Language": "en-US,en;q=0.8",
        },
        follow_redirects=False,
        trust_env=False,
    )
