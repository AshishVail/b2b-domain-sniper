"""
B2B Domain Sniper
Website crawler with prioritized internal page discovery.
"""

import asyncio
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from .config import RuntimeConfig
from .fetcher import create_http_client, fetch_page


IMPORTANT_PATHS = {
    "contact": 1,
    "about": 2,
    "career": 3,
    "careers": 3,
    "job": 3,
    "jobs": 3,
    "pricing": 4,
    "service": 5,
    "product": 6,
    "team": 7,
    "company": 8,
    "location": 9,
    "office": 9,
}

IGNORED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".svg", ".ico", ".pdf", ".zip", ".css",
    ".js", ".xml", ".mp4", ".mp3", ".woff",
    ".woff2", ".ttf", ".eot", ".avif",
)

SKIPPED_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "template",
    "iframe",
}


class PageParser(HTMLParser):
    """Extract visible text, title, metadata and internal links."""

    def __init__(self):
        super().__init__(convert_charrefs=True)

        self.title_parts = []
        self.text_parts = []
        self.links = []

        self.in_title = False
        self.skip_depth = 0

        self.current_href = None
        self.current_link_text = []

        self.description = None
        self.base_href = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attributes = dict(attrs)

        if tag in SKIPPED_TAGS:
            self.skip_depth += 1
            return

        if self.skip_depth:
            return

        if tag == "title":
            self.in_title = True

        elif tag == "meta":
            name = (
                attributes.get("name")
                or attributes.get("property")
                or ""
            ).lower()

            if name in {
                "description",
                "og:description",
                "twitter:description",
            }:
                content = (
                    attributes.get("content") or ""
                ).strip()

                if content and not self.description:
                    self.description = content

        elif tag == "base":
            href = attributes.get("href")

            if href and not self.base_href:
                self.base_href = href.strip()

        elif tag == "a":
            href = attributes.get("href")

            if href:
                self.current_href = href.strip()
                self.current_link_text = []

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in SKIPPED_TAGS:
            self.skip_depth = max(
                0,
                self.skip_depth - 1,
            )
            return

        if self.skip_depth:
            return

        if tag == "title":
            self.in_title = False

        elif tag == "a" and self.current_href:
            self.links.append({
                "href": self.current_href,
                "text": " ".join(
                    self.current_link_text
                ).strip(),
            })

            self.current_href = None
            self.current_link_text = []

    def handle_data(self, data):
        if self.skip_depth:
            return

        value = data.strip()

        if not value:
            return

        if self.in_title:
            self.title_parts.append(value)

        self.text_parts.append(value)

        if self.current_href:
            self.current_link_text.append(value)

    def get_result(self):
        return {
            "title": " ".join(
                self.title_parts
            ).strip(),
            "description": self.description,
            "text": " ".join(self.text_parts),
            "links": self.links[:500],
            "base_href": self.base_href,
        }


def parse_html(html):
    """Convert HTML into structured page data."""

    parser = PageParser()

    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        pass

    return parser.get_result()


def _normalize_start_url(domain: str) -> str:
    """Normalize a domain or URL into an HTTP(S) URL."""

    value = (domain or "").strip()

    if not value:
        raise ValueError("Domain cannot be empty.")

    if "://" not in value:
        value = f"https://{value}"

    parsed = urlsplit(value)

    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are supported.")

    if not parsed.hostname:
        raise ValueError("Invalid domain or website URL.")

    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not supported.")

    return urlunsplit((
        parsed.scheme.lower(),
        parsed.netloc,
        parsed.path or "/",
        parsed.query,
        "",
    ))


def _get_hostname(url: str) -> str | None:
    """Safely extract a normalized hostname from a URL."""

    try:
        return (urlsplit(url).hostname or "").lower().rstrip(".") or None
    except (ValueError, AttributeError):
        return None


def _normalize_internal_link(base_url, href):
    """Return normalized same-site HTTP links only."""

    try:
        if not isinstance(href, str) or not href.strip():
            return None

        absolute_url = urljoin(
            base_url,
            href.strip(),
        )

        parsed = urlsplit(absolute_url)
        base = urlsplit(base_url)

        if parsed.scheme.lower() not in {"http", "https"}:
            return None

        if parsed.username or parsed.password:
            return None

        base_hostname = (base.hostname or "").lower().rstrip(".")
        target_hostname = (parsed.hostname or "").lower().rstrip(".")

        if not base_hostname or target_hostname != base_hostname:
            return None

        # Avoid treating different ports as the same website.
        base_port = base.port
        target_port = parsed.port

        if base_port != target_port:
            return None

        path = parsed.path or "/"

        if path.lower().endswith(IGNORED_EXTENSIONS):
            return None

        return urlunsplit((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.query,
            "",
        ))

    except (ValueError, AttributeError, TypeError):
        return None


def discover_internal_pages(
    base_url,
    links,
    max_pages,
):
    """Prioritize useful company website pages."""

    if max_pages <= 0:
        return []

    candidates = []
    seen = set()

    for link in links or []:
        if not isinstance(link, dict):
            continue

        href = link.get("href", "")
        text = link.get("text", "")

        normalized_url = _normalize_internal_link(
            base_url,
            href,
        )

        if not normalized_url:
            continue

        if normalized_url in seen:
            continue

        seen.add(normalized_url)

        parsed = urlsplit(normalized_url)

        searchable = (
            f"{parsed.path} {text}"
        ).lower()

        priority = 99

        for keyword, rank in IMPORTANT_PATHS.items():
            if keyword in searchable:
                priority = min(priority, rank)

        candidates.append((
            priority,
            normalized_url,
        ))

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    return [
        url
        for _, url in candidates[:max_pages]
    ]


async def _fetch_and_parse(
    client,
    url,
    config,
):
    """Fetch and parse one website page."""

    page = await fetch_page(
        client,
        url,
        config,
    )

    if not isinstance(page, dict):
        raise TypeError(
            "fetch_page() must return a dictionary."
        )

    html = page.get("html") or ""

    if html:
        parsed = parse_html(html)

        # Resolve links relative to the HTML base URL if present.
        link_base = page.get("url") or url

        if parsed.get("base_href"):
            candidate_base = urljoin(
                link_base,
                parsed["base_href"],
            )

            if _normalize_internal_link(
                link_base,
                candidate_base,
            ):
                link_base = candidate_base

        resolved_links = []

        for link in parsed.get("links", []):
            href = link.get("href", "")

            resolved_links.append({
                "href": urljoin(link_base, href),
                "text": link.get("text", ""),
            })

        parsed["links"] = resolved_links

        page.update(parsed)

    else:
        page.update({
            "title": "",
            "description": None,
            "text": "",
            "links": [],
            "base_href": None,
        })

    page.setdefault("url", url)
    page.setdefault("headers", {})
    page.setdefault("html", "")
    page.setdefault("status_code", None)
    page.setdefault("error", None)

    return page


def _failed_page(url: str, error: Exception) -> dict:
    """Build a consistent page object when fetching fails."""

    return {
        "url": url,
        "html": "",
        "title": "",
        "description": None,
        "text": "",
        "links": [],
        "headers": {},
        "status_code": None,
        "error": str(error),
    }


async def process_domain(
    domain: str,
    config: RuntimeConfig,
) -> dict[str, Any]:
    """Crawl homepage and prioritized internal pages."""

    errors = []
    pages = []

    start_url = _normalize_start_url(domain)
    hostname = _get_hostname(start_url)

    max_pages = max(
        1,
        int(getattr(config, "max_pages_per_domain", 6)),
    )

    page_concurrency = max(
        1,
        int(getattr(config, "page_concurrency", 3)),
    )

    async with create_http_client(config) as client:

        # 1. Fetch homepage
        try:
            homepage = await _fetch_and_parse(
                client,
                start_url,
                config,
            )

        except Exception as exc:
            homepage = _failed_page(
                start_url,
                exc,
            )

        pages.append(homepage)

        if homepage.get("error"):
            errors.append({
                "url": homepage.get("url", start_url),
                "error": homepage["error"],
            })

        homepage_html = homepage.get("html") or ""

        if not homepage_html:
            return {
                "domain": hostname,
                "website_url": start_url,
                "pages": pages,
                "page_count": len(pages),
                "errors": errors,
            }

        # 2. Discover pages from homepage and then from
        #    subsequently crawled internal pages.
        base_url = homepage.get("url") or start_url

        seen_urls = {
            start_url,
            base_url,
        }

        page_semaphore = asyncio.Semaphore(
            page_concurrency
        )

        async def fetch_limited(url):
            async with page_semaphore:
                return await _fetch_and_parse(
                    client,
                    url,
                    config,
                )

        # 3. Crawl in batches until the page limit is reached.
        while len(pages) < max_pages:

            remaining_pages = max_pages - len(pages)

            all_links = []

            for page in pages:
                page_url = page.get("url") or base_url

                for link in page.get("links", []) or []:
                    if not isinstance(link, dict):
                        continue

                    all_links.append({
                        "href": urljoin(
                            page_url,
                            link.get("href", ""),
                        ),
                        "text": link.get("text", ""),
                    })

            candidate_urls = discover_internal_pages(
                base_url,
                all_links,
                remaining_pages + len(seen_urls),
            )

            # Remove URLs already attempted or crawled.
            candidate_urls = [
                url
                for url in candidate_urls
                if url not in seen_urls
            ]

            if not candidate_urls:
                break

            candidate_urls = candidate_urls[:remaining_pages]

            # Mark URLs before fetching to prevent repeated attempts.
            seen_urls.update(candidate_urls)

            results = await asyncio.gather(
                *[
                    fetch_limited(url)
                    for url in candidate_urls
                ],
                return_exceptions=True,
            )

            for index, result in enumerate(results):

                if isinstance(result, Exception):
                    errors.append({
                        "url": candidate_urls[index],
                        "error": str(result),
                    })
                    continue

                pages.append(result)

                if result.get("error"):
                    errors.append({
                        "url": result.get(
                            "url",
                            candidate_urls[index],
                        ),
                        "error": result["error"],
                    })

    return {
        "domain": hostname,
        "website_url": start_url,
        "pages": pages,
        "page_count": len(pages),
        "errors": errors,
    }
