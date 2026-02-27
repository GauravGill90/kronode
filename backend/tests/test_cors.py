"""Tests for CORS configuration helper."""

import os
import importlib
import pytest


def _reload_cors():
    import app.core.cors as cors_module
    importlib.reload(cors_module)
    return cors_module


class TestGetAllowedOrigins:
    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.kronode.io,https://staging.kronode.io")
        monkeypatch.setenv("ENVIRONMENT", "production")
        cors = _reload_cors()
        origins = cors._get_allowed_origins()
        assert "https://app.kronode.io" in origins
        assert "https://staging.kronode.io" in origins

    def test_falls_back_to_localhost_in_dev(self, monkeypatch):
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "development")
        cors = _reload_cors()
        origins = cors._get_allowed_origins()
        assert "http://localhost:3000" in origins

    def test_raises_in_production_without_env(self, monkeypatch):
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        cors = _reload_cors()
        with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
            cors._get_allowed_origins()
