import pytest

from src.email_extractor import (
    normalize_email,
    extract_emails,
    classify_email,
    extract_email_details,
)

from src.content_cleaner import (
    normalize_text,
    clean_html,
)


class TestEmailNormalization:

    def test_normalize_email_lowercase(self):
        assert normalize_email("INFO@EXAMPLE.COM") == "info@example.com"

    def test_normalize_email_removes_spaces(self):
        assert normalize_email("  info@example.com  ") == "info@example.com"

    def test_normalize_email_rejects_invalid_email(self):
        result = normalize_email("not-an-email")
        assert result is None or result == ""


class TestEmailExtraction:

    def test_extract_single_email(self):
        emails = extract_emails("Contact us at info@example.com")

        assert any(
            item == "info@example.com"
            or (
                isinstance(item, dict)
                and item.get("email") == "info@example.com"
            )
            for item in emails
        )

    def test_extract_multiple_emails(self):
        text = """
        Contact: info@example.com
        Sales: sales@example.org
        Support: support@example.net
        """

        emails = extract_emails(text)

        extracted = {
            item if isinstance(item, str) else item.get("email")
            for item in emails
        }

        assert "info@example.com" in extracted
        assert "sales@example.org" in extracted
        assert "support@example.net" in extracted

    def test_extract_does_not_return_duplicates(self):
        text = """
        info@example.com
        INFO@example.com
        info@example.com
        """

        emails = extract_emails(text)

        extracted = [
            item if isinstance(item, str) else item.get("email")
            for item in emails
        ]

        assert len(extracted) == len(set(extracted))

    def test_extract_obfuscated_email(self):
        text = "Contact us at sales [at] example [dot] com"

        emails = extract_emails(text)

        extracted = {
            item if isinstance(item, str) else item.get("email")
            for item in emails
        }

        assert "sales@example.com" in extracted

    def test_extract_from_empty_text(self):
        assert extract_emails("") == []


class TestEmailClassification:

    def test_classify_email_returns_value(self):
        result = classify_email("info@example.com")

        assert result is not None
        assert isinstance(result, str)
        assert result == "role_based"

    def test_extract_email_details_returns_collection(self):
        result = extract_email_details(
            "Contact info@example.com for business inquiries."
        )

        assert result is not None
        assert isinstance(result, (list, dict))


class TestContentCleaning:

    def test_normalize_text_removes_extra_whitespace(self):
        result = normalize_text("  Hello     World  ")

        assert "  " not in result
        assert result.strip() == "Hello World"

    def test_clean_html_removes_script_content(self):
        html = """
        <html>
            <body>
                <h1>Welcome</h1>
                <script>alert("test")</script>
                <p>Business website</p>
            </body>
        </html>
        """

        result = clean_html(html)

        assert isinstance(result, dict)
        assert "Welcome" in result["text"]
        assert "Business website" in result["text"]
        assert "alert" not in result["text"]

    def test_clean_html_handles_empty_input(self):
        result = clean_html("")

        assert isinstance(result, dict)
        assert result["text"] == ""


class TestPhoneExtraction:

    def test_tel_link_is_extracted_and_deduplicated(self):
        from src.phone_extractor import extract_phone_details

        html = (
            '<a href="tel:+1-212-555-1234">Call us</a>'
            '<p>+1-212-555-1234</p>'
        )

        result = extract_phone_details(html=html)

        assert len(result) == 1
        assert result[0]["phone"] == "+1-212-555-1234"
        assert result[0]["source_type"] == "tel_link"

    def test_unlabelled_numbers_are_not_treated_as_phone_numbers(self):
        from src.phone_extractor import extract_phones

        text = (
            "2025 2026 100 200 3000; "
            "revenue 123 456 7890"
        )

        assert extract_phones(text=text) == []

    def test_phone_label_allows_nationally_formatted_number(self):
        from src.phone_extractor import extract_phones

        assert "212-555-0198" in extract_phones(
            text="Phone: 212-555-0198"
        )
