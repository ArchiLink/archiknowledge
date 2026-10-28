# Security

Security controls and accepted risks for the portal. Actors, components and deployment are described in ARCHITECTURE.md and not repeated here.

## Required Security Inputs
- Exposure: intranet only, HTTP on `PORTAL_ADDRESS:PORTAL_PORT`. Anyone on the intranet can view Approved lessons; adding or changing anything requires login.
- Roles: the actors in ARCHITECTURE.md, enforced through the Django groups `Staff` and `QA Reviewers`; admins are named accounts.
- Sensitive data: Internal (staff only, never shared outside the firm): cost/time impact, staff names, site photos, redlined drawings. Project names of lessons flagged `anonymise` are Confidential.
- Secrets: Django `SECRET_KEY`, Postgres password, SMTP credentials.
- Trust boundaries: browser ↔ Caddy (HTTP); Caddy ↔ gunicorn; Django ↔ Postgres; outbound SMTP; WordPress iframe of `/embed/*`.
- CI/CD: none; checks run locally before merging (see Deployment).
- Log retention: container stdout via Docker logging, kept 90 days.
- Backups: the server team snapshots the whole VM nightly and weekly, with the VM shut down so Postgres is consistent; the portal runs no backup service of its own.

## Provisional Security Rules

### HTTP boundary
- Serve over plain HTTP; Caddy listens on HTTP only. Keep `SECURE_SSL_REDIRECT`, HSTS, `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` off; turning them on without TLS breaks login.
- Build `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` from `PORTAL_ADDRESS`/`PORTAL_PORT` only; never use `*`.
- Keep Django's CSRF protection on for every state-changing request, including HTMX requests (send the token via `hx-headers`).
- Send `X-Frame-Options: DENY` everywhere by default. If `FRAME_ANCESTORS` is set, allow framing of `/embed/*` only, via CSP `frame-ancestors <FRAME_ANCESTORS>`.
- Send a CSP limited to `'self'` for scripts, styles and images; vendor HTMX, Chart.js and any other front-end library into static files (no CDNs).
- Send `X-Content-Type-Options: nosniff` and `Referrer-Policy: same-origin`.
- Use distinct cookie names (`SESSION_COOKIE_NAME = "qp_session"`, `CSRF_COOKIE_NAME = "qp_csrf"`); cookies are not isolated by port and could collide with other apps on the same IP.
- Publish only Caddy's port; never publish gunicorn or Postgres ports from Compose.

### Authentication and authorization
- Use `LoginRequiredMiddleware` as the default-deny. Mark only the read-only public views with `@login_not_required`: dashboard, knowledge base, gallery, lesson detail, embed and `/health/`.
- Public views accept GET only, change no state, and query Approved lessons only.
- Require login for `/submit/`, the user's own submissions, `/review/`, CSV export and `/admin/`.
- Serve uploaded images through a Caddy `forward_auth` check against Django. Images of Approved lessons are public; images of any other lesson are shown only to its submitter and to QA. Store uploads under random UUID filenames.
- Enforce roles on the server for every action. Only `QA Reviewers` can reach the review queue, change status, anonymise, edit others' lessons or export; hidden buttons are not authorization.
- When `anonymise` is set, never output the project name in public pages, embed, emails, CSV export or logs.
- Use Django's password validators with a minimum length of 12. Lock an account for 15 minutes after 10 failed logins.
- Expire sessions after 10 hours of inactivity; rotate the session on login; give `is_staff`/`is_superuser` only to named admins, never shared accounts.

### Input validation
- Validate every input through Django forms/ModelForms; never build SQL from strings (ORM or parameterized queries only).
- Rely on template auto-escaping; never use `|safe` or `mark_safe` on user-supplied text.
- Accept only JPEG/PNG/WebP within `MAX_UPLOAD_MB` per image and `MAX_IMAGES_PER_LESSON` per lesson; verify with Pillow, re-encode, and strip EXIF data (removes GPS location from site photos).
- Enforce size limits at both layers: `DATA_UPLOAD_MAX_MEMORY_SIZE`/`FILE_UPLOAD_MAX_MEMORY_SIZE` and Caddy `request_body max_size`.
- Validate public filter and search parameters against the lookup tables and a maximum length; page sizes are fixed on the server.
- In CSV exports, prefix cells that start with `=`, `+`, `-` or `@` with `'` to block formula injection.
- In email templates, escape user text and link to lessons by permalink; don't attach images.

### Secrets
- Read all configuration and secrets from `.env` (keys listed in `.env.example`); commit only `.env.example` with dummy values.
- Refuse to start when `DJANGO_SECRET_KEY` or `POSTGRES_PASSWORD` is missing or still `change-me`.
- Keep `.env` on the server, readable only by the deploy user; never bake secrets into Docker images or commit them to git.
- Rotate `SECRET_KEY` and DB/SMTP passwords if the server or repo may have been exposed, and when someone with access leaves.

### Logging and error handling
- Run with `DEBUG=False` outside local development; show generic 403/404/500 pages and log the details on the server.
- Log logins, failed logins, lockouts, submissions, approvals/rejections, anonymise changes, exports and admin changes, with user and timestamp.
- Never log passwords, session IDs, CSRF tokens, `.env` values or full request bodies.
- While `EMAIL_HOST` is empty, skip sending and log one line per skipped email (recipient count and type, never the body).
- Write logs to stdout and cap Docker log size with rotation (`max-size`, `max-file`).
- Set the review audit fields (`reviewed_by`, `reviewed_at`) only through the review action.

### Deployment
- Before merging to `main`, run the test suite and `pip-audit` locally, and fix or note any findings in the PR.
- Run `manage.py check --deploy` before each release. HTTPS, HSTS and secure-cookie warnings are expected; fix anything else.
- Pin Python dependencies in a lockfile; pin base images to a specific tag; rebuild monthly and when security updates are released.
- Run containers as a non-root user. Store uploads without an execute bit (`0640`), only as re-encoded images, and serve them read-only through Caddy; Docker named volumes can't be mounted `noexec`.
- Before applying migrations in production, confirm the last VM snapshot succeeded (or ask the server team for one); ask them to test a restore quarterly.
- Containers use `restart: unless-stopped` and Docker starts at boot, so the portal comes back after each nightly snapshot shutdown.

### Accepted risks
- Without TLS, passwords and session cookies cross the office network unencrypted. The login page tells users not to reuse their Windows/M365 password.
- Anyone who can reach the intranet can read Approved lessons and their images without logging in.
- Reconsider both risks if guests or contractors share the network.

## Prompt Placeholders To Resolve
None for security. Deployment values (IP, port, framing, mail server) are set in `.env` by the deployer; product questions are listed in ARCHITECTURE.md.
