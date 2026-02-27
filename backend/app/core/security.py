"""Security utilities for the Kronode backend.

Provides input sanitization helpers and secure defaults used across
all API endpoints to prevent injection and data-leak issues.
"""

import re
from typing import Any


_MAX_STRING_LENGTH = 10_000
_SAFE_URL_PATTERN = re.compile(r"^https?://[\w\-._~:/?#\[\]@!$&'()*+,;=%]+$")


def sanitize_string(value: str, max_length: int = _MAX_STRING_LENGTH) -> str:
    """Strip leading/trailing whitespace and enforce a maximum length."""
    if not isinstance(value, str):
        raise TypeError(f"Expected str, got {type(value).__name__}")
    return value.strip()[:max_length]


def is_safe_url(url: str) -> bool:
    """Return True only if the URL is a valid http/https URL."""
    if not isinstance(url, str):
        return False
    return bool(_SAFE_URL_PATTERN.match(url.strip()))


def redact_secrets(data: dict[str, Any], secret_keys: set[str] | None = None) -> dict[str, Any]:
    """Return a copy of *data* with sensitive fields replaced by '[REDACTED]'.

    The default set covers common credential field names.  Pass *secret_keys*
    to add or override that set.
    """
    default_keys = {
        "github_access_token",
        "jira_api_token",
        "slack_bot_token",
        "password",
        "token",
        "secret",
        "api_key",
    }
    keys_to_redact = secret_keys if secret_keys is not None else default_keys

    return {
        k: "[REDACTED]" if k in keys_to_redact else v
        for k, v in data.items()
    }
