# Pinned base images (SECURITY.md); rebuild monthly and on security updates.
FROM python:3.12.16-slim-bookworm AS base

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app
RUN mkdir /app/media && chown app:app /app /app/media

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


# Development and test image: adds pytest and ruff.
FROM base AS dev
RUN uv sync --frozen --no-install-project
COPY --chown=app:app . .
USER app


# Production image.
FROM base AS runtime
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["gunicorn", "portal.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]


# Collect static files at build time; the values below exist only to import settings.
FROM base AS static
COPY . .
RUN DJANGO_SECRET_KEY=collectstatic-only POSTGRES_PASSWORD=collectstatic-only \
    PORTAL_ADDRESS=build POSTGRES_DB=build POSTGRES_USER=build \
    python manage.py collectstatic --noinput


# Caddy proxy with the static files baked in, so they can't go stale on a shared volume.
FROM caddy:2.11.7-alpine AS proxy
RUN addgroup -S proxy && adduser -S -G proxy proxy && chown -R proxy:proxy /data /config
COPY proxy/Caddyfile /etc/caddy/Caddyfile
COPY proxy/entrypoint.sh /usr/local/bin/proxy-entrypoint
COPY --from=static /app/staticfiles /srv/static
USER proxy
EXPOSE 8080
ENTRYPOINT ["/bin/sh", "/usr/local/bin/proxy-entrypoint"]
