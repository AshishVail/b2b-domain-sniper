
"""
B2B Domain Sniper
Controlled same-site website crawler.
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
    "script", "style", "noscript", "svg",
    "template", "iframe",
}


class PageParser(HTMLParser):
    """Extract page title, visible text and links from HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)

        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[dict[str, str]] = []

        self.in_title = False
        self.skip_depth = 0

        self.current_href: str | None = None
        self.current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()

        if tag in SKIPPED_TAGS:
            self.skip_depth += 1
            return

        if self.skip_depth:
            return

        if tag == "title":
            self.in_title = True

        elif tag == "a":
            attributes = dict(attrs)
            href = attributes.get("href")

            if href:
                self.current_href = href.strip()
                self.current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag in SKIPPED_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return

        if self.skip_depth:
            return

        if tag == "title":
            self.in_title = False

        elif tag == "a" and self.current_href:
            self.links.append({
                "href": self.current_href,
                "text": " ".join(self.current_link_text).strip(),
            })

            self.current_href = None
            self.current_link_text = []

    def handle_data(self, data: str) -> None:
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

    def get_result(self) -> dict[str, Any]:
        return {
            "title": " ".join(self.title_parts).strip(),
            "text": " ".join(self.text_parts),
            "links": self.links[:200],
        }


def parse_html(html: str) -> dict[str, Any]:
    """Parse HTML into a lightweight structured representation."""

    parser = PageParser()

    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass

    return parser.get_result()


def _normalize_internal_link(
    base_url: str,
    href: str,
) -> str | None:
    """Resolve and normalize a link belonging to the same hostname."""

    try:
        absolute_url = urljoin(base_url, href.strip())
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
            "",
            "",
        ))

    except (ValueError, AttributeError):
        return None


def discover_internal_pages(
    base_url: str,
    links: list[dict[str, str]],
    max_pages: int,
) -> list[str]:
    """
    Select high-value internal pages.

    Priority:
    Contact -> About -> Careers -> Pricing -> Services -> Others
    """

    candidates: list[tuple[int, str]] = []
    seen: set[str] = {base_url}

    for link in links:
        href = link.get("href", "")
        text = link.get("text", "").lower()

        normalized_url = _normalize_internal_link(base_url, href)

        if not normalized_url or normalized_url in seen:
            continue

        seen.add(normalized_url)

        parsed = urlsplit(normalized_url)
        searchable = f"{parsed.path} {text}".lower()

        priority = 99

        for keyword, rank in IMPORTANT_PATHS.items():
            if keyword in searchable:
                priority = min(priority, rank)

        candidates.append((priority, normalized_url))

    candidates.sort(key=lambda item: (item[0], item[1]))

    return [
        url
        for _, url in candidates[:max_pages]
    ]


async def _fetch_and_parse(
    client: Any,
    url: str,
    config: RuntimeConfig,
) -> dict[str, Any]:
    """Fetch a page and attach its extracted content."""

    page = await fetch_page(client, url, config)

    html = page.get("html", "")

    if html:
        parsed_content = parse_html(html)
        page.update(parsed_content)
    else:
        page.update({
            "title": "",
            "text": "",
            "links": [],
        })

    return page


async def process_domain(
    domain: str,
    config: RuntimeConfig,
) -> dict[str, Any]:
    """
    Crawl one company website.

    The homepage is fetched first. Important same-site links
    are then selected and fetched within the configured page limit.
    """

    errors: list[dict[str, str]] = []
    pages: list[dict[str, Any]] = []

    async with create_http_client(config) as client:

        # Step 1: Fetch homepage.
        homepage = await _fetch_and_parse(
            client,
            domain,
            config,
        )

        pages.append(homepage)

        if homepage.get("error"):
            errors.append({
                "url": homepage["url"],
                "error": homepage["error"],
            })

        homepage_html = homepage.get("html", "")

        if not homepage_html:
            return {
                "domain": urlsplit(domain).hostname,
                "website_url": domain,
                "pages": pages,
                "page_count": 1,
                "errors": errors,
            }

        # Step 2: Discover important internal pages.
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

        # Step 3: Fetch selected pages with bounded concurrency.
        page_semaphore = asyncio.Semaphore(3)

        async def fetch_limited(url: str) -> dict[str, Any]:
            async with page_semaphore:
                return await _fetch_and_parse(
                    client,
                    url,
                    config,
                )

        if candidate_urls:
            additional_pages = await asyncio.gather(
                *[
                    fetch_limited(url)
                    for url in candidate_urls
                ],
                return_exceptions=True,
            )

            for index, result in enumerate(additional_pages):

                if isinstance(result, Exception):
                    errors.append({
                        "url": candidate_urls[index],
                        "error": str(result),
                    })
                    continue

                pages.append(result)

                if result.get("error"):
                    errors.append({
                        "url": result["url"],
                        "error": result["error"],
                    })

    return {
        "domain": urlsplit(domain).hostname,
        "website_url": domain,
        "pages": pages,
        "page_count": len(pages),
        "errors": errors,
    }
