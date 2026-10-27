import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from portal import env

ROOT = Path(__file__).resolve().parent.parent


def run_check(**overrides):
    """Run `manage.py check` in a fresh process with modified environment variables."""
    child_env = {**os.environ, **overrides}
    for key, value in overrides.items():
        if value is None:
            child_env.pop(key)
    return subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=ROOT,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )


# REQ-OPS-003 AC-02: refuse to start with missing or placeholder secrets.


@pytest.mark.parametrize("key", ["DJANGO_SECRET_KEY", "POSTGRES_PASSWORD"])
def test_startup_refused_when_secret_missing(key):
    result = run_check(**{key: None})
    assert result.returncode != 0
    assert key in result.stderr


@pytest.mark.parametrize("key", ["DJANGO_SECRET_KEY", "POSTGRES_PASSWORD"])
def test_startup_refused_when_secret_is_placeholder(key):
    result = run_check(**{key: "change-me"})
    assert result.returncode != 0
    assert key in result.stderr


def test_error_output_never_contains_secret_values():
    result = run_check(
        DJANGO_SECRET_KEY="a-real-looking-secret-value", POSTGRES_PASSWORD="change-me"
    )
    assert result.returncode != 0
    assert "POSTGRES_PASSWORD" in result.stderr
    assert "a-real-looking-secret-value" not in result.stderr + result.stdout


def test_startup_succeeds_with_valid_settings():
    result = run_check()
    assert result.returncode == 0, result.stderr


# REQ-OPS-003 AC-03: hosts and origins come from PORTAL_ADDRESS/PORTAL_PORT, never "*".


def test_allowed_hosts_built_from_portal_address():
    assert os.environ["PORTAL_ADDRESS"] in settings.ALLOWED_HOSTS
    assert "*" not in settings.ALLOWED_HOSTS


def test_wildcard_address_refused():
    with pytest.raises(ImproperlyConfigured):
        env.allowed_hosts("*")


@pytest.mark.parametrize(
    ("port", "expected"),
    [(80, ["http://192.0.2.10"]), (8080, ["http://192.0.2.10:8080"])],
)
def test_trusted_origins(port, expected):
    assert env.trusted_origins("192.0.2.10", port) == expected


# REQ-OPS-003 AC-04: DEBUG off by default; HTTPS-only settings off.


def test_debug_off_by_default():
    assert settings.DEBUG is False


def test_https_only_settings_off():
    assert settings.SECURE_SSL_REDIRECT is False
    assert settings.SECURE_HSTS_SECONDS == 0
    assert settings.SESSION_COOKIE_SECURE is False
    assert settings.CSRF_COOKIE_SECURE is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("True", True), ("true", True), ("1", True), ("False", False), ("no", False), ("", False)],
)
def test_get_bool(monkeypatch, raw, expected):
    monkeypatch.setenv("X_FLAG", raw)
    assert env.get_bool("X_FLAG") is expected


def test_get_bool_rejects_garbage(monkeypatch):
    monkeypatch.setenv("X_FLAG", "maybe")
    with pytest.raises(ImproperlyConfigured):
        env.get_bool("X_FLAG")


def test_get_int(monkeypatch):
    monkeypatch.setenv("X_NUM", "8080")
    assert env.get_int("X_NUM", 80) == 8080
    monkeypatch.setenv("X_NUM", "")
    assert env.get_int("X_NUM", 80) == 80
    monkeypatch.setenv("X_NUM", "eighty")
    with pytest.raises(ImproperlyConfigured):
        env.get_int("X_NUM", 80)


def test_require_str_missing(monkeypatch):
    monkeypatch.delenv("X_MISSING", raising=False)
    with pytest.raises(ImproperlyConfigured, match="X_MISSING"):
        env.require_str("X_MISSING")
