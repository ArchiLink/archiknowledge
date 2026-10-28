# CLAUDE.md

How to work in this repo. What the portal is: ARCHITECTURE.md. Security rules: SECURITY.md. Install, release and rollback on the VM: RUNBOOK.md.

@ARCHITECTURE.md
@SECURITY.md

## Project status
- Bootstrap mode: no application code yet; ARCHITECTURE.md and SECURITY.md are provisional.
- If implementation needs to depart from either doc, raise it with the user first, then update the doc in the same change.
- The plain-HTTP, no-CI, local-accounts setup is deliberate. Don't add HTTPS, CI or SSO unless the user asks.

## Guardrails
- New GitHub issues MUST use the requirement template (`.github/ISSUE_TEMPLATE/requirement.yml`), with an ID `REQ-[MODULE]-[###]` using its module codes.
- Implement against the issue's acceptance criteria. Each AC gets at least one test, and the PR states which tests cover which AC.
- Work one issue at a time, on its own branch. Changes reach `main` only through a PR.
- When an issue is done and tests, ruff and `pip-audit` pass: commit, push, open the PR, squash-merge it, then pull `main` (user decision, 2026-10-27). Otherwise don't commit or push unless the user asks.
- Ask before adding a dependency, a new container/service or a new third-party asset.
- Any new setting is read from the environment and gets a documented key in `.env.example`. Never create or edit a real `.env`.
- Don't build features that aren't in an issue or ARCHITECTURE.md.

## Working style
- For every design or tooling decision, give your single best recommendation with its tradeoff, plus at most one alternative. The user decides.
- Right-size for ~30 internal users; prefer fewer moving parts.
- Keep changes small and scoped to the issue; match the surrounding code's naming and style.
- Report results plainly: what ran, what passed, what failed, what was skipped.

## Workflow
- Repository: https://github.com/ArchiLink/archiknowledge (default branch `main`).
- Dependencies: uv, locked in `uv.lock`.
- Tests: pytest + pytest-django; ≥ 80% branch coverage per the requirement template.
- Lint/format: ruff for both.
- Account lockout: django-axes. Scheduler: supercronic inside the `web` image. Backups: whole-VM snapshots by the server team (no backup service).

- Branch: `req/<REQ-ID>-short-name`. Commit: `<REQ-ID>: imperative summary`, with `Closes #N` in the PR.
- Release: run the RUNBOOK.md release checklist, then tag `v<X.Y.Z>` on `main`; deploy and roll back per RUNBOOK.md.

## Commands
- Test (pytest in a throwaway Postgres stack; fails under 80% branch coverage): `docker compose -f docker-compose.test.yml run --rm --build test`
- Lint/format: `uv run ruff check .` and `uv run ruff format --check .`
- Audit: `uv export --frozen --format requirements-txt --no-hashes > req.txt && uvx pip-audit -r req.txt` (write `req.txt` outside the repo)
- Run: `docker compose up -d --build` (needs `.env`)
- Migrate: `docker compose exec web python manage.py migrate`
- Create superuser: `docker compose exec web python manage.py createsuperuser`
- Deploy check: `docker compose exec web python manage.py check --deploy` (only the 4 HTTPS/HSTS/secure-cookie warnings are expected)
- Add a dependency: `uv add <pkg>` (`--dev` for tooling); ask the user first.
