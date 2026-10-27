"""Django settings. Every value comes from the environment; see .env.example and SECURITY.md."""

from pathlib import Path

from portal import env

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env.require_secret("DJANGO_SECRET_KEY")
DEBUG = env.get_bool("DJANGO_DEBUG", default=False)

PORTAL_ADDRESS = env.require_str("PORTAL_ADDRESS")
PORTAL_PORT = env.get_int("PORTAL_PORT", 80)
ALLOWED_HOSTS = env.allowed_hosts(PORTAL_ADDRESS)
CSRF_TRUSTED_ORIGINS = env.trusted_origins(PORTAL_ADDRESS, PORTAL_PORT)

# Plain HTTP by design (SECURITY.md): turning these on without TLS breaks login.
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "portal.urls"
WSGI_APPLICATION = "portal.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "db",  # Compose service name
        "PORT": 5432,
        "NAME": env.require_str("POSTGRES_DB"),
        "USER": env.require_str("POSTGRES_USER"),
        "PASSWORD": env.require_secret("POSTGRES_PASSWORD"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env.get_str("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Everything goes to stdout; Docker rotates it (SECURITY.md). Request bodies are never logged.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "stdout": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["stdout"], "level": "INFO"},
    "loggers": {
        # Django's own console handler only runs with DEBUG on; send errors to stdout instead.
        "django": {"handlers": [], "level": "INFO", "propagate": True},
    },
}
