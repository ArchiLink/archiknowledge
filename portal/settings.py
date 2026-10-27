"""Django settings. Every value comes from the environment; see .env.example and SECURITY.md."""

from datetime import timedelta
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
    "axes",
    "core",  # after axes, so core.admin can wrap axes' admin classes
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Default-deny: every view needs login unless marked @login_not_required (SECURITY.md).
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",  # must be last
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",  # must be first
    "django.contrib.auth.backends.ModelBackend",
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
                "core.context_processors.portal",
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
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "login"

# Sessions end after 10 hours of inactivity; cookie names are distinct because cookies
# aren't isolated by port on a shared IP (SECURITY.md).
SESSION_COOKIE_AGE = 10 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_NAME = "qp_session"
CSRF_COOKIE_NAME = "qp_csrf"

# Lock an account (by username, not IP) for 15 minutes after 10 failed logins (SECURITY.md).
# A locked account sees the same page and message as a wrong password.
AXES_FAILURE_LIMIT = 10
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ["username"]
# axes.W006 asks to also lock by IP. SECURITY.md locks the account; IP lockout would also
# block the whole office behind one NAT address.
SILENCED_SYSTEM_CHECKS = ["axes.W006"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_CALLABLE = "core.lockout.lockout_response"
AXES_DISABLE_ACCESS_LOG = True  # successful logins are already in the audit log
# Caddy replaces any client-sent X-Forwarded-For with the real client address.
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]
AXES_IPWARE_PROXY_COUNT = 1

PORTAL_NAME = env.get_str("PORTAL_NAME", "Design Quality Log")

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
