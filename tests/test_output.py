import json
import pytest

from src.result_builder import (
    build_result,
    serialize_result,
    build_json_result,
)


class TestResultBuilder:

    def test_build_result_returns_dictionary(self):
        result = build_result(
            domain="example.com"
        )

        assert isinstance(result, dict)

    def test_result_contains_expected_sections(self):
        result = build_result(
            domain="example.com"
        )

        expected_sections = [
            "success",
            "api",
            "scan",
            "business",
            "website",
            "email_intelligence",
            "mx_validation",
            "technology_intelligence",
            "hiring_intelligence",
            "business_intelligence",
            "errors",
        ]

        for section in expected_sections:
            assert section in result

    def test_result_contains_domain(self):
        result = build_result(
            domain="example.com"
        )

        assert isinstance(result.get("scan"), dict)
        assert result["scan"].get("domain") == "example.com"

    def test_serialize_result_returns_json(self):
        result = build_result(
            domain="example.com"
        )

        serialized = serialize_result(result)

        assert isinstance(serialized, str)

        parsed = json.loads(serialized)

        assert isinstance(parsed, dict)

    def test_json_result_is_valid_json(self):
        result = build_json_result(
            domain="example.com"
        )

        assert isinstance(result, str)

        parsed = json.loads(result)

        assert isinstance(parsed, dict)

    def test_result_handles_empty_data(self):
        result = build_result(
            domain="example.com",
            errors=[],
        )

        assert isinstance(result, dict)
        assert "errors" in result

    def test_result_handles_errors(self):
        result = build_result(
            domain="example.com",
            errors=["Test error"],
        )

        assert isinstance(result, dict)
        assert result["errors"] == ["Test error"]

    def test_public_website_pages_do_not_include_raw_html(self):
        result = build_result({
            "domain": "example.com",
            "status": "completed",
            "website": {
                "url": "https://example.com",
                "pages": [{
                    "url": "https://example.com",
                    "html": (
                        "<html><body>"
                        "private raw html payload"
                        "</body></html>"
                    ),
                    "text": "Public text",
                    "status_code": 200,
                }],
            },
        })

        page = result["website"]["pages"][0]

        assert "html" not in page
        assert page["text"] == "Public text"

    def test_missing_status_does_not_claim_success(self):
        result = build_result(
            domain="example.com"
        )

        assert result["success"] is False
        assert result["scan"]["status"] == "failed"
