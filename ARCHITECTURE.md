# Architecture

## Required Architecture Inputs
- System purpose: Intranet portal where staff log design omissions, errors and site lessons; QA approves them and approved items are broadcast firm-wide (live feed + email digest) to stop repeat errors.
- Primary use cases: submit a lesson with Failed/Fixed images; QA review/edit/anonymise/approve/reject; live feed by phase (SD, DD, CD, TA, CA, PC); searchable, filterable knowledge base; Redline Gallery (Failed vs Fixed side by side); high-impact email digest every two weeks; track whether a lesson was incorporated into specs/standard details/onboarding.
- Target users / actors: intranet viewers (no login; view approved lessons); staff (login; submit, see own submissions); QA reviewers, i.e. Technical Director / QA Manager (review, edit, anonymise, approve); admin (manage users, groups, lookup lists).
- Runtime environment: Web, on desktop browsers on the corporate intranet only; no mobile access.
- Server framework: Django 5.x on Python 3.12.
- Client framework: Django templates rendered on the server + HTMX for partial updates (feed refresh, filters); Chart.js for dashboard charts.
- API style and integration model: Pages rendered on the server, with HTMX partials; no public API. Integrations: email via SMTP (outbound; set up later); standalone app linked from the WordPress intranet; optional iframe of the ticker (`FRAME_ANCESTORS`).
- Authentication and session model: Viewing approved lessons needs no login; submitting, reviewing and admin need login. Local Django accounts created by an admin; sessions stored on the server; groups `Staff` and `QA Reviewers` control permissions; Entra ID SSO is an optional later addition.
- Data model expectations: PostgreSQL 16. Admin-editable lookup tables: Phase, Discipline, IssueType, BuildingComponent. Project 1→N Lesson; Lesson 1→N LessonImage (kind FAILED/FIXED). Lesson status Submitted → Approved/Rejected. Postgres full-text search over the lesson text fields. Images stored on a Docker volume.
- Deployment model: Docker Compose on an intranet VM, served over plain HTTP on an IP address (no domain, no TLS, no CI), configured via `.env` (see `.env.example`): `web` (gunicorn), `db` (postgres), `proxy` (Caddy: static files, access-checked media), `scheduler` (digest job), `backup` (nightly DB dump + media archive).
- Scale expectations: About 30 internal staff; low volume; single instance; available during business hours.

## Initial Architecture (Provisional)
- A single Django app sits behind Caddy on HTTP. Caddy serves static files, serves uploaded images only after a Django access check, and forwards everything else to gunicorn.
- Read pages (dashboard, knowledge base, gallery, detail, embed) are public and read-only. Submitting, reviewing, exporting and admin require login. Permissions come from group membership: only `QA Reviewers` can reach the review queue or change a lesson's status.
- Write path: a staff member submits a lesson and images, which are saved with status Submitted. A QA reviewer then edits, anonymises and approves it, and the review audit fields are set.
- Read path: the dashboard, knowledge base, gallery and detail pages only ever query Approved lessons. The dashboard feed re-polls every 30s using HTMX. Anonymised lessons hide the project name everywhere they appear.
- Lookup lists, including phases, are rows in the database managed in Django admin, not hard-coded choices.
- Every two weeks, the scheduler runs a management command that emails approved High-impact lessons published since the last run. Notifications on submit and approval go out through the same SMTP setup.
- The embed endpoint (`/embed/ticker/`) is optional and is the only framable page. Framing is allowed only when `FRAME_ANCESTORS` is set.
- Each night, the backup container dumps Postgres and archives the media volume.

**Assumptions**
- An intranet machine with Docker and a fixed IP is available; the WordPress intranet (HTTP, IP only) links to it.
- An internal SMTP relay or an M365 SMTP account is available for outbound email.
- Running a single instance with no high-availability setup is acceptable for about 30 users.
- Plain HTTP is accepted on the trusted office network (see Accepted risks in SECURITY.md).

**Open questions / unknowns**
- Expected number of lessons per month: decides storage needs.
- Deployment values (IP/port, mail server, backup location) are set by the deployer in `.env`; email stays disabled until configured.
- Phase codes TA and PC are proposed and need confirming.
- Portal name: The Detail / ArchInsight / The Blueprint / Trace.
