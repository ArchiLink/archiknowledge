# CLAUDE.md

How to work in this repo. What the portal is: ARCHITECTURE.md. Security rules: SECURITY.md.

@ARCHITECTURE.md
@SECURITY.md

## Project status
- Bootstrap mode: no application code yet; ARCHITECTURE.md and SECURITY.md are provisional.
- If implementation needs to depart from either doc, raise it with the user first, then update the doc in the same change.
- The plain-HTTP, no-CI, local-accounts setup is deliberate. Don't add HTTPS, CI or SSO unless the user asks.

## Guardrails
- New GitHub issues MUST use the requirement template (`.github/ISSUE_TEMPLATE/requirement.yml`), with an ID `REQ-[MODULE]-[###]` using its module codes.
- Implement against the issue's acceptance criteria. Each AC gets at least one test, and the PR states which tests cover which AC.
- Work one issue at a time, on its own branch. Changes reach `main` only through a PR after human review.
- Don't commit, push or open PRs unless the user asks.
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
- Account lockout: django-axes. Scheduler: supercronic inside the `web` image. Backup encryption: `age`.

Undecided (recommendation in brackets; replace each line once the user decides).
- Branch naming: [`req/<REQ-ID>-short-name`].
- Commit message: [`<REQ-ID>: imperative summary`].
- Commands (run, test, lint, migrate, create superuser): defined when the Docker skeleton exists.
- Release/deploy procedure on the intranet machine: unknown.
