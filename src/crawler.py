
"""
B2B Domain Sniper
Website crawler with internal page discovery.
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
    "job": 3,
    "pricing": 4,
    "service": 5,
    "product": 6,
    "team": 7,
    "company": 8,
}

IGNORED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".svg", ".ico", ".pdf", ".zip", ".css",
    ".js", ".xml", ".mp4", ".mp3", ".woff",
    ".woff2", ".ttf", ".eot",
)

SKIPPED_TAGS = {
    "script", "style", "noscript",
    "svg", "template", "iframe",
}


class PageParser(HTMLParser):
    """Extract visible text, title, metadata and links."""

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
        self.phone_numbers = []

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
            }:
                self.description = (
                    attributes.get("content") or ""
                ).strip() or self.description

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
            "links": self.links[:300],
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


def _normalize_internal_link(base_url, href):
    """Return normalized same-site HTTP links only."""

    try:
        absolute_url = urljoin(
            base_url,
            href.strip(),
        )

        parsed = urlsplit(absolute_url)
        base = urlsplit(base_url)

        if parsed.scheme not in {"http", "https"}:
            return None

        if parsed.username or parsed.password:
            return None

        if parsed.hostname != base.hostname:
            return None

        if parsed.port != base.port:
            return None

        path = parsed.path or "/"

        if path.lower().endswith(IGNORED_EXTENSIONS):
            return None

        return urlunsplit((
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.query,
            "",
        ))

    except (ValueError, AttributeError):
        return None


def discover_internal_pages(
    base_url,
    links,
    max_pages,
):
    """Prioritize useful company website pages."""

    candidates = []
    seen = {base_url}

    for link in links:
        if not isinstance(link, dict):
            continue

        href = link.get("href", "")
        text = link.get("text", "").lower()

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

    html = page.get("html") or ""

    if html:
        parsed = parse_html(html)
        page.update(parsed)
    else:
        page.update({
            "title": "",
            "description": None,
            "text": "",
            "links": [],
        })

    page.setdefault("headers", {})
    page.setdefault("html", "")
    page.setdefault("status_code", None)
    page.setdefault("error", None)

    return page


async def process_domain(
    domain: str,
    config: RuntimeConfig,
) -> dict[str, Any]:
    """Crawl homepage and important internal pages."""

    errors = []
    pages = []

    parsed_domain = urlsplit(domain)

    hostname = parsed_domain.hostname

    async with create_http_client(config) as client:

        # Homepage
        homepage = await _fetch_and_parse(
            client,
            domain,
            config,
        )

        pages.append(homepage)

        if homepage.get("error"):
            errors.append({
                "url": homepage.get("url", domain),
                "error": homepage["error"],
            })

        homepage_html = homepage.get("html", "")

        if not homepage_html:
            return {
                "domain": hostname,
                "website_url": domain,
                "pages": pages,
                "page_count": len(pages),
                "errors": errors,
            }

        # Discover internal pages
        base_url = homepage.get("url") or domain

        remaining_pages = max(
            config.max_pages_per_domain - 1,
            0,
        )

        candidate_urls = discover_internal_pages(
            base_url,
            homepage.get("links", []),
            remaining_pages,
        )

        # Fetch internal pages
        page_semaphore = asyncio.Semaphore(3)

        async def fetch_limited(url):
            async with page_semaphore:
                return await _fetch_and_parse(
                    client,
                    url,
                    config,
                )

        if candidate_urls:

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
        "website_url": domain,
        "pages": pages,
        "page_count": len(pages),
        "errors": errors,
    }
