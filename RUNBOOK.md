# Runbook

How to install, upgrade and roll back the portal on the intranet VM. What the portal is: ARCHITECTURE.md. Security rules: SECURITY.md.

All commands run on the VM, as the deploy user, from the repository folder (e.g. `/opt/archiknowledge`).

## Prerequisites
- Linux VM with a fixed intranet IP, Docker Engine 24+ and the Compose plugin.
- Docker starts at boot, so the portal comes back after the nightly snapshot shutdown: `sudo systemctl enable docker`.
- A deploy user in the `docker` group, with read access to the GitHub repository.
- Backups are the server team's nightly and weekly whole-VM snapshots (VM shut down); the portal has no backup service.

## First install
1. Get the code at the release tag:
   ```sh
   git clone https://github.com/ArchiLink/archiknowledge.git /opt/archiknowledge
   cd /opt/archiknowledge
   git checkout <release tag, e.g. v1.0.0>
   ```
2. Create `.env` from the template and lock it down:
   ```sh
   cp .env.example .env
   chmod 600 .env
   ```
3. Edit `.env`:
   - `PORTAL_ADDRESS`: the VM's IP. `PORTAL_PORT`: `80` unless something else uses it.
   - `DJANGO_SECRET_KEY`: generate with `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`.
   - `POSTGRES_PASSWORD`: a long random value (same command).
   - `TIME_ZONE`, `PORTAL_NAME`, `FRAME_ANCESTORS` (WordPress address, or empty).
   - Email keys: leave `EMAIL_HOST` empty until the mail server is ready.
   The portal refuses to start while `DJANGO_SECRET_KEY` or `POSTGRES_PASSWORD` is missing or `change-me`.
4. Build and start, then create the tables, groups and lookup lists:
   ```sh
   docker compose up -d --build
   docker compose exec web python manage.py migrate
   ```
5. Create the first admin (a named person, never a shared account):
   ```sh
   docker compose exec web python manage.py createsuperuser
   ```
6. Sign in at `http://<PORTAL_ADDRESS>/admin/` and:
   - create projects and check the lookup lists (Phase, Discipline, Issue type, Building component);
   - create staff accounts and add each to the `Staff` group, and reviewers to `QA Reviewers`.
7. Verify (see [Checks after a deploy](#checks-after-a-deploy)).

## Release checklist
Run on a development machine, on `main`, before tagging a release:
1. Tests pass with ≥ 80% branch coverage: `docker compose -f docker-compose.test.yml run --rm --build test`
2. Lint and format: `uv run ruff check .` and `uv run ruff format --check .`
3. No known vulnerable dependencies: `uv export --frozen --format requirements-txt --no-hashes > <outside the repo>/req.txt && uvx pip-audit -r <outside the repo>/req.txt`
4. Tag and push: `git tag v<X.Y.Z> && git push origin v<X.Y.Z>`

## Upgrade
1. Note the running tag (`git describe --tags`) for rollback.
2. Confirm last night's VM snapshot succeeded, or ask the server team for a fresh one. Do not migrate without one.
3. Fetch, check out the new tag and rebuild:
   ```sh
   git fetch --tags
   git checkout <new tag>
   docker compose up -d --build
   docker compose exec web python manage.py migrate
   ```
4. Check `.env.example` for new keys (`git diff <old tag> <new tag> -- .env.example`) and add them to `.env`, then `docker compose up -d`.
5. Verify (see [Checks after a deploy](#checks-after-a-deploy)).

## Monthly rebuild
Pick up base-image security updates (SECURITY.md), monthly and when updates are announced:
```sh
docker compose build --pull
docker compose up -d
```

## Rollback
- **The new release added no migrations** (`git diff --stat <old tag> <new tag> -- '*/migrations/'` is empty): `git checkout <old tag> && docker compose up -d --build`.
- **It did add migrations**: ask the server team to restore the VM snapshot taken before the upgrade. Anything submitted since that snapshot is lost, so tell QA Reviewers.

## Demo data
For showcasing before real lessons exist. Loads 14 demo lessons with Failed/Fixed drawings (11 published, 2 in the review queue, 1 rejected), owned by demo users that can't sign in:
```sh
docker compose exec web python manage.py demo_data            # load
docker compose exec web python manage.py demo_data --logins   # also add demo sign-ins
docker compose exec web python manage.py demo_data --remove   # remove; real data is kept
```
`--logins` creates `demo.staff` (Staff) and `demo.manager` (QA Reviewers) and prints their random passwords once; run it again to get new ones. Neither has admin rights. Show the Admin role with your own named superuser: shared admin accounts are not allowed (SECURITY.md). `--remove` also deletes the demo sign-ins and anything they submitted.
Remove the demo before turning email on: loading refuses while `EMAIL_HOST` is set, so the digest can't send demo lessons to staff.

## Checks after a deploy
1. All services are `Up` and `healthy`: `docker compose ps`
2. Health check answers `ok`: `curl -fsS http://<PORTAL_ADDRESS>:<PORTAL_PORT>/health/`
3. Only the 4 expected warnings (HTTPS redirect, HSTS, secure session cookie, secure CSRF cookie): `docker compose exec web python manage.py check --deploy`
4. In a browser: the dashboard loads, an admin can sign in, and `/review/` opens for a QA Reviewer.
5. No errors in the logs: `docker compose logs --since 10m web proxy scheduler`
