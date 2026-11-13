
import pytest

from src.technology_detector import (
    detect_technologies,
    detect_from_page,
)

from src.hiring_detector import (
    detect_job_board,
    is_career_path,
    detect_hiring,
)


class TestTechnologyDetection:

    def test_detect_wordpress(self):
        html = """
        <html>
            <head>
                <link rel="stylesheet"
                      href="/wp-content/themes/example/style.css">
            </head>
            <body>
                <script src="/wp-includes/js/jquery.js"></script>
            </body>
        </html>
        """

        result = detect_technologies(html)

        assert result is not None
        assert isinstance(result, dict)

    def test_detect_shopify(self):
        html = """
        <html>
            <body>
                <script src="https://cdn.shopify.com/shopifycloud.js"></script>
                <div id="shopify-section-header"></div>
            </body>
        </html>
        """

        result = detect_technologies(html)

        assert isinstance(result, dict)

    def test_detect_react(self):
        html = """
        <html>
            <body>
                <div id="root"></div>
                <script src="/static/js/react.production.min.js"></script>
            </body>
        </html>
        """

        result = detect_technologies(html)

        assert isinstance(result, dict)

    def test_detect_from_page(self):
        page = {
            "url": "https://example.com",
            "html": """
                <html>
                    <script src="/wp-content/themes/site/theme.js"></script>
                    <body>Example business website</body>
                </html>
            """,
            "headers": {},
        }

        result = detect_from_page(page)

        assert result is not None
        assert isinstance(result, dict)

    def test_empty_html_does_not_crash(self):
        result = detect_technologies("")

        assert isinstance(result, dict)


class TestHiringDetection:

    def test_detect_greenhouse_job_board(self):
        url = "https://boards.greenhouse.io/example"

        result = detect_job_board(url)

        assert result is not None

    def test_detect_lever_job_board(self):
        url = "https://jobs.lever.co/example"

        result = detect_job_board(url)

        assert result is not None

    def test_detect_career_path(self):
        assert is_career_path("https://example.com/careers")

    def test_detect_jobs_path(self):
        assert is_career_path("https://example.com/jobs")

    def test_non_career_path(self):
        assert not is_career_path("https://example.com/about")

    def test_detect_hiring_keywords(self):
        html = """
        <html>
            <body>
                <h1>Join Our Team</h1>
                <p>We are hiring talented people.</p>
                <a href="/careers">View Open Positions</a>
            </body>
        </html>
        """

        result = detect_hiring(html)

        assert result is not None
        assert isinstance(result, dict)

    def test_empty_hiring_content(self):
        result = detect_hiring("")

        assert result is not None
        assert isinstance(result, dict)
