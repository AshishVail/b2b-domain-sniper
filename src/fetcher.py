
"""
B2B Domain Sniper
Secure asynchronous website fetcher.
"""

import asyncio
import ipaddress
import socket

from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from .config import RuntimeConfig


RETRYABLE_STATUS_CODES = {
    408, 425, 429, 500, 502, 503, 504
}

REDIRECT_STATUS_CODES = {
    301, 302, 303, 307, 308
}


def _is_public_ip(address: str) -> bool:
    """Check whether an IP address is globally routable."""

    try:
        return ipaddress.ip_address(address).is_global
    except ValueError:
        return False


async def validate_public_http_url(url: str) -> None:
    """Reject private, local and non-public destinations."""

    parsed = urlsplit(url)

    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError(
            "Only HTTP and HTTPS URLs are allowed."
        )

    if parsed.username or parsed.password:
        raise ValueError(
            "URL credentials are not allowed."
        )

    hostname = parsed.hostname

    if not hostname:
        raise ValueError("URL hostname is missing.")

    hostname = hostname.rstrip(".").lower()

    blocked_hostnames = {
        "localhost",
        "metadata",
        "metadata.google.internal",
    }

    if (
        hostname in blocked_hostnames
        or hostname.endswith(".localhost")
    ):
        raise ValueError(
            "Local or metadata hostnames are blocked."
        )

    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if not literal_ip.is_global:
            raise ValueError(
                "Non-public IP destinations are blocked."
            )
        return

    port = parsed.port or (
        443 if parsed.scheme == "https" else 80
    )

    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            port,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )

    except socket.gaierror as exc:
        raise ValueError(
            f"DNS resolution failed for {hostname}."
        ) from exc

    addresses = {
        record[4][0]
        for record in records
    }

    if not addresses:
        raise ValueError(
            f"No IP addresses found for {hostname}."
        )

    if any(
        not _is_public_ip(address)
        for address in addresses
    ):
        raise ValueError(
            f"Hostname {hostname} resolves to a non-public IP."
        )


def _retry_delay(
    response: httpx.Response,
    attempt: int,
) -> float:
    """Calculate retry delay."""

    retry_after = response.headers.get("Retry-After")

    if retry_after:
        try:
            return min(
                max(float(retry_after), 0.0),
                5.0,
            )
        except ValueError:
            pass

    return min(
        0.5 * (2 ** attempt),
        5.0,
    )


async def _read_limited_response(
    response: httpx.Response,
    max_bytes: int,
) -> bytes:
    """Read response without exceeding the size limit."""

    content_length = response.headers.get(
        "Content-Length"
    )

    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise ValueError(
                    "Response exceeds configured size limit."
                )
        except ValueError as exc:
            if "configured size limit" in str(exc):
                raise

            raise ValueError(
                "Invalid Content-Length header."
            ) from exc

    chunks = []
    total_size = 0

    async for chunk in response.aiter_bytes():

        total_size += len(chunk)

        if total_size > max_bytes:
            raise ValueError(
                "Response exceeds configured size limit."
            )

        chunks.append(chunk)

    return b"".join(chunks)


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


async def fetch_page(
    client: httpx.AsyncClient,
    url: str,
    config: RuntimeConfig,
) -> dict[str, Any]:
    """Fetch one public website page safely."""

    current_url = url

    try:

        for redirect_number in range(
            config.max_redirects + 1
        ):

            await validate_public_http_url(
                current_url
            )

            redirect_followed = False

            for attempt in range(
                config.max_retries + 1
            ):

                try:

                    async with client.stream(
                        "GET",
                        current_url,
                        follow_redirects=False,
                    ) as response:

                        status_code = response.status_code
                        headers = dict(response.headers)

                        # Handle redirects
                        if status_code in REDIRECT_STATUS_CODES:

                            location = response.headers.get(
                                "Location"
                            )

                            if not location:
                                return _page_result(
                                    current_url,
                                    status_code,
                                    headers=headers,
                                    error="Redirect without Location header.",
                                )

                            if (
                                redirect_number
                                >= config.max_redirects
                            ):
                                raise ValueError(
                                    "Maximum redirects exceeded."
                                )

                            current_url = urljoin(
                                current_url,
                                location,
                            )

                            redirect_followed = True
                            break

                        # Retry temporary server errors
                        if (
                            status_code in RETRYABLE_STATUS_CODES
                            and attempt < config.max_retries
                        ):
                            await asyncio.sleep(
                                _retry_delay(
                                    response,
                                    attempt,
                                )
                            )
                            continue

                        content_type = response.headers.get(
                            "Content-Type",
                            "",
                        ).lower()

                        is_html = (
                            "text/html" in content_type
                            or "application/xhtml+xml" in content_type
                        )

                        if not is_html:
                            return _page_result(
                                url=str(response.url),
                                status_code=status_code,
                                content_type=content_type or None,
                                headers=headers,
                                error=(
                                    None if response.is_success
                                    else f"HTTP {status_code}"
                                ),
                            )

                        body = await _read_limited_response(
                            response,
                            config.max_response_bytes,
                        )

                        charset = response.encoding or "utf-8"

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

                        return _page_result(
                            url=str(response.url),
                            status_code=status_code,
                            html=(
                                html if response.is_success
                                else ""
                            ),
                            content_type=content_type,
                            headers=headers,
                            error=(
                                None if response.is_success
                                else f"HTTP {status_code}"
                            ),
                        )

                except (
                    httpx.TimeoutException,
                    httpx.TransportError,
                ):

                    if attempt >= config.max_retries:
                        raise

                    await asyncio.sleep(
                        min(
                            0.5 * (2 ** attempt),
                            5.0,
                        )
                    )

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


def create_http_client(
    config: RuntimeConfig,
) -> httpx.AsyncClient:
    """Create reusable asynchronous HTTP client."""

    timeout = httpx.Timeout(
        config.request_timeout_seconds,
        connect=10.0,
    )

    limits = httpx.Limits(
        max_connections=max(
            10,
            config.max_concurrency * 3,
        ),
        max_keepalive_connections=max(
            5,
            config.max_concurrency,
        ),
        keepalive_expiry=15.0,
    )

    return httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        headers={
            "User-Agent": config.user_agent,
            "Accept": (
                "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"
            ),
            "Accept-Language": "en-US,en;q=0.8",
        },
        follow_redirects=False,
        trust_env=False,
    )
