# Architecture

What the portal is and how it is built. Security controls are in SECURITY.md; rules for working in this repo are in CLAUDE.md.

## Required Architecture Inputs
- System purpose: Intranet portal where staff log design omissions, errors and site lessons; QA approves them and approved items are broadcast firm-wide (live feed + email digest) to stop repeat errors.
- Primary use cases: submit a lesson with Failed/Fixed images; QA review/edit/anonymise/approve/reject; live feed by phase (SD, DD, CD, TA, CA, PC); searchable, filterable knowledge base; Redline Gallery (Failed vs Fixed side by side); high-impact email digest every two weeks; track whether a lesson was incorporated into specs/standard details/onboarding.
- Actors:
  - Intranet viewer (no login): views Approved lessons.
  - Staff (group `Staff`): submits lessons, sees own submissions.
  - QA Reviewers (group `QA Reviewers`; Technical Director / QA Manager): review, edit, anonymise, approve/reject, export.
  - Admin: manages users, groups and lookup lists.
- Runtime environment: desktop browsers on the corporate intranet only; no mobile access.
- Stack: Django 5.x on Python 3.12; server-rendered templates + HTMX for partial updates (feed refresh, filters); Chart.js for dashboard charts; PostgreSQL 16.
- API and integrations: no public API. Outbound email via SMTP (set up later); linked from the WordPress intranet, which may iframe the ticker.
- Authentication: local Django accounts created by an admin; server-side sessions; Entra ID SSO is a possible later addition.
- Data model: lookup tables Phase, Discipline, IssueType, BuildingComponent are rows managed in Django admin, not hard-coded choices. Project 1→N Lesson; Lesson 1→N LessonImage (kind FAILED/FIXED). Lesson status Submitted → Approved/Rejected. Postgres full-text search over the lesson text fields. Images stored on a Docker volume.
- Deployment: Docker Compose on one intranet VM, plain HTTP on an IP address (no domain, no TLS, no CI), configured via `.env` (keys in `.env.example`). Services: `web` (gunicorn), `db` (postgres), `proxy` (Caddy), `scheduler` (digest job). Backups are nightly whole-VM snapshots taken by the server team with the VM shut down; the portal has no backup service.
- Scale: about 30 staff; low volume; single instance; available during business hours.

## Initial Architecture (Provisional)
- One Django app behind Caddy. Caddy serves static files, serves uploaded images only after a Django access check, and forwards everything else to gunicorn.
- Write path: Staff submit a lesson and images (status Submitted); a QA reviewer edits, anonymises and approves or rejects it.
- Read path: dashboard, knowledge base, gallery and detail pages show Approved lessons only. The dashboard feed re-polls every 30s via HTMX.
- Email: every two weeks the scheduler runs a management command that emails approved High-impact lessons published since the last run. Submit and approval notifications use the same SMTP setup.
- Embed: `/embed/ticker/` is an optional ticker page for the WordPress iframe.

**Assumptions**
- An intranet machine with Docker and a fixed IP is available; the WordPress intranet (HTTP, IP only) links to it.
- An internal SMTP relay or an M365 SMTP account is available for outbound email.
- A single instance with no high availability is acceptable for about 30 users.

**Open questions**
- Expected number of lessons per month (decides storage needs).
- Phase codes TA and PC are proposed and need confirming.
- Portal name: The Detail / ArchInsight / The Blueprint / Trace.
