"""Read configuration from the environment. Keys are documented in .env.example."""

import os

from django.core.exceptions import ImproperlyConfigured

PLACEHOLDER = "change-me"


def get_str(key, default=""):
    return os.environ.get(key, default).strip()


def get_bool(key, default=False):
    value = get_str(key).lower()
    if not value:
        return default
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    raise ImproperlyConfigured(f"{key} must be True or False.")


def get_int(key, default):
    value = get_str(key)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        raise ImproperlyConfigured(f"{key} must be a whole number.") from None


def require_secret(key):
    """Return a secret, refusing to start if it is missing or still the placeholder.

    The error names the key only, never the value.
    """
    value = get_str(key)
    if not value or value == PLACEHOLDER:
        raise ImproperlyConfigured(f"{key} is missing or still '{PLACEHOLDER}'. Set it in .env.")
    return value


def require_str(key):
    value = get_str(key)
    if not value:
        raise ImproperlyConfigured(f"{key} is missing. Set it in .env.")
    return value


def allowed_hosts(address):
    if "*" in address:
        raise ImproperlyConfigured("PORTAL_ADDRESS must be a single address, not a wildcard.")
    return [address]


def trusted_origins(address, port):
    return [f"http://{address}" if port == 80 else f"http://{address}:{port}"]
