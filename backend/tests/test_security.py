"""Unit tests for app.core.security utilities."""

import pytest
from app.core.security import sanitize_string, is_safe_url, redact_secrets


class TestSanitizeString:
    def test_strips_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_enforces_max_length(self):
        long_str = "a" * 20_000
        result = sanitize_string(long_str, max_length=100)
        assert len(result) == 100

    def test_raises_on_non_string(self):
        with pytest.raises(TypeError):
            sanitize_string(123)  # type: ignore

    def test_empty_string_ok(self):
        assert sanitize_string("") == ""


class TestIsSafeUrl:
    def test_accepts_https(self):
        assert is_safe_url("https://github.com/org/repo") is True

    def test_accepts_http(self):
        assert is_safe_url("http://localhost:3000") is True

    def test_rejects_javascript_protocol(self):
        assert is_safe_url("javascript:alert(1)") is False

    def test_rejects_ftp(self):
        assert is_safe_url("ftp://files.example.com") is False

    def test_rejects_non_string(self):
        assert is_safe_url(None) is False  # type: ignore

    def test_rejects_empty(self):
        assert is_safe_url("") is False


class TestRedactSecrets:
    def test_redacts_known_keys(self):
        data = {
            "github_access_token": "ghp_secret",
            "name": "Kronode",
        }
        result = redact_secrets(data)
        assert result["github_access_token"] == "[REDACTED]"
        assert result["name"] == "Kronode"

    def test_redacts_custom_keys(self):
        data = {"my_secret_field": "value", "other": "ok"}
        result = redact_secrets(data, secret_keys={"my_secret_field"})
        assert result["my_secret_field"] == "[REDACTED]"
        assert result["other"] == "ok"

    def test_does_not_mutate_original(self):
        data = {"token": "abc123", "safe": "yes"}
        redact_secrets(data)
        assert data["token"] == "abc123"
