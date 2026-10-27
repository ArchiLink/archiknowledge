# CLAUDE.md

Design Quality Log & Knowledge Portal: an intranet Django app where staff log design lessons, QA approves them, and approved lessons are broadcast. The original brief is in `quality_tracker_framework.pdf`.

@ARCHITECTURE.md
@SECURITY.md

## Project status
- Bootstrap mode: no application code yet. ARCHITECTURE.md and SECURITY.md are provisional.
- If implementation needs to depart from either doc, raise it with the user first, then update the doc in the same change. Don't let code and docs drift apart silently.
- This project is a deliberate exception to the user's usual standards: plain HTTP on an IP address, no TLS, no CI, local accounts. Don't add HTTPS, CI pipelines or SSO unless the user asks.

## Guardrails
- New GitHub issues MUST use the requirement template (`.github/ISSUE_TEMPLATE/requirement.yml`), so every issue is a structured, testable requirement with an ID `REQ-[MODULE]-[###]` using the module codes listed in that template.
- Implement against the issue's acceptance criteria. Each AC gets at least one test, and the PR states which tests cover which AC.
- Work one issue at a time, on its own branch. Changes reach `main` only through a PR after human review.
- Don't commit, push or open PRs unless the user asks.
- Ask before adding a dependency, a new container/service, or a new third-party asset. Vendor any front-end library you add (no CDNs, per SECURITY.md).
- Any new setting is read from the environment and gets a documented key in `.env.example`. Never create or edit a real `.env`.
- Phases, disciplines, issue types and building components are lookup rows managed in Django admin. Don't hard-code them as choices.
- Don't build features that aren't in an issue or ARCHITECTURE.md.

## Working style
- For every design or tooling decision, give your single best recommendation with its tradeoff, plus at most one alternative. The user decides.
- Right-size solutions for ~30 internal users; prefer fewer moving parts.
- Keep changes small and scoped to the issue; match the surrounding code's naming and style.
- Report results plainly: what ran, what passed, what failed, what was skipped.

## Workflow (TO BE DECIDED)
Recommendations are in brackets. Replace each line once the user decides.
- Repository: TO BE DECIDED. git not initialised yet; GitHub assumed because of the issue template.
- Dependency/lockfile tool: TO BE DECIDED [uv with `uv.lock`].
- Test runner: TO BE DECIDED [pytest + pytest-django; coverage ≥ 80% branch per the requirement template].
- Lint/format: TO BE DECIDED [ruff for both].
- Commands (run, test, lint, migrate, create superuser): UNKNOWN. To be defined when the Docker skeleton exists.
- Branch naming: TO BE DECIDED [`req/<REQ-ID>-short-name`].
- Commit message convention: TO BE DECIDED [`<REQ-ID>: imperative summary`].
- Release/deploy procedure on the intranet machine: UNKNOWN.
