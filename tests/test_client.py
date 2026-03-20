"""Tests for HTBIntegration constructor and _parse_response()."""

import os

import pytest
from unittest.mock import MagicMock, patch

from htbctl import HTBIntegration
from htbctl.exceptions import (
    HTBAuthError,
    HTBError,
    HTBMachineNotFoundError,
    HTBRateLimitError,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_response(status_code, json_body=None, content_type="application/json", text=None):
    r = MagicMock()
    r.status_code = status_code
    r.headers = {"Content-Type": content_type}
    r.json.return_value = json_body or {}
    r.text = text or ""
    r.raise_for_status = MagicMock()
    return r


def make_client():
    """HTBIntegration with a fake token, no network."""
    return HTBIntegration(token="fake.jwt.token")


# ── Constructor ───────────────────────────────────────────────────────────────

def test_constructor_token_from_argument():
    htb = HTBIntegration(token="my.token")
    assert htb._token == "my.token"


def test_constructor_token_from_env(monkeypatch):
    monkeypatch.setenv("HTB_TOKEN", "env.token")
    with patch("htbctl.client._ENV_SEARCH_PATHS", []):
        htb = HTBIntegration()
    assert htb._token == "env.token"


def test_constructor_no_token_raises(monkeypatch):
    monkeypatch.delenv("HTB_TOKEN", raising=False)
    with patch("htbctl.client._ENV_SEARCH_PATHS", []):
        with pytest.raises(ValueError, match="HTB_TOKEN"):
            HTBIntegration()


def test_constructor_file_does_not_mutate_env(monkeypatch, tmp_path):
    """dotenv_values should be used, not load_dotenv — no side effects."""
    monkeypatch.delenv("HTB_TOKEN", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("HTB_TOKEN=file.token\n")

    with patch("htbctl.client._ENV_SEARCH_PATHS", []):
        htb = HTBIntegration(env_path=str(env_file))

    assert htb._token == "file.token"
    assert os.environ.get("HTB_TOKEN") != "file.token"


# ── _parse_response() ─────────────────────────────────────────────────────────

def test_parse_response_401_raises_auth_error():
    htb = make_client()
    r = make_response(401)
    with pytest.raises(HTBAuthError):
        htb._parse_response(r, "user/info")


def test_parse_response_403_raises_htb_error():
    htb = make_client()
    r = make_response(403, json_body={"message": "Forbidden"})
    with pytest.raises(HTBError, match="403"):
        htb._parse_response(r, "vm/spawn")


def test_parse_response_404_raises_not_found():
    htb = make_client()
    r = make_response(404)
    with pytest.raises(HTBMachineNotFoundError):
        htb._parse_response(r, "machine/profile/Nonexistent")


def test_parse_response_429_raises_rate_limit():
    htb = make_client()
    r = make_response(429)
    with pytest.raises(HTBRateLimitError):
        htb._parse_response(r, "vm/spawn")


def test_parse_response_html_raises_auth_error():
    """HTB returns HTML login page when token is invalid (not always 401)."""
    htb = make_client()
    r = make_response(200, content_type="text/html", text="<!DOCTYPE html>")
    with pytest.raises(HTBAuthError, match="HTML"):
        htb._parse_response(r, "user/info")


def test_parse_response_invalid_json_raises_htb_error():
    """Malformed JSON body should raise HTBError, not raw JSONDecodeError."""
    htb = make_client()
    r = make_response(200, content_type="application/json", text="{broken")
    r.json.side_effect = ValueError("Expecting value")
    with pytest.raises(HTBError, match="Invalid JSON"):
        htb._parse_response(r, "user/info")
