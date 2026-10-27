import pytest


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    # Tests only: production keeps Django's default PBKDF2 hasher.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
