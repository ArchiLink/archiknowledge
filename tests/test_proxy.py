"""Caddy proxy behaviour (REQ-OPS-004), tested against the running test Compose stack."""

import os
import socket
import urllib.error
import urllib.parse
import urllib.request

import pytest

PROXY = os.environ.get("PROXY_URL", "")
FRAMED_PROXY = os.environ.get("FRAMED_PROXY_URL", "")
FRAME_ANCESTORS = "http://192.0.2.5"

pytestmark = pytest.mark.skipif(not PROXY, reason="needs docker-compose.test.yml")


def fetch(base, path, method="GET", data=None):
    request = urllib.request.Request(
        base + path, data=data, method=method, headers={"Host": os.environ["PORTAL_ADDRESS"]}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.headers
    except urllib.error.HTTPError as error:
        return error.code, error.headers


PATHS = ["/health/", "/static/admin/css/base.css", "/does-not-exist/", "/embed/ticker/"]


# AC-01: CSP 'self', nosniff and same-origin referrer policy on every response.
@pytest.mark.parametrize("path", PATHS)
def test_security_headers_on_every_response(path):
    _, headers = fetch(PROXY, path)
    csp = headers["Content-Security-Policy"]
    for directive in ("script-src 'self'", "style-src 'self'", "img-src 'self'"):
        assert directive in csp
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "same-origin"
    assert "Server" not in headers


# AC-02: with FRAME_ANCESTORS empty, nothing can be framed, including /embed/*.
@pytest.mark.parametrize("path", PATHS)
def test_framing_denied_when_frame_ancestors_empty(path):
    _, headers = fetch(PROXY, path)
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


# AC-03: with FRAME_ANCESTORS set, only /embed/* may be framed, and only by that origin.
def test_embed_frameable_by_configured_origin():
    _, headers = fetch(FRAMED_PROXY, "/embed/ticker/")
    assert "X-Frame-Options" not in headers
    assert f"frame-ancestors {FRAME_ANCESTORS}" in headers["Content-Security-Policy"]


@pytest.mark.parametrize("path", ["/health/", "/static/admin/css/base.css", "/admin/"])
def test_non_embed_paths_still_denied_when_frame_ancestors_set(path):
    _, headers = fetch(FRAMED_PROXY, path)
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


# AC-04: bodies over the limit are rejected by Caddy (test limit: 1 MB x 2 images + 5 MB = 7 MB).
def send_headers_only(base, content_length):
    """Send request headers announcing a body, without the body; return the status code."""
    url = urllib.parse.urlsplit(base)
    with socket.create_connection((url.hostname, url.port), timeout=10) as conn:
        conn.sendall(
            (
                "POST /health/ HTTP/1.1\r\n"
                f"Host: {os.environ['PORTAL_ADDRESS']}\r\n"
                f"Content-Length: {content_length}\r\n"
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
        )
        return int(conn.recv(1024).split(b"\r\n", 1)[0].split()[1])


def test_oversized_body_rejected_before_reaching_django():
    # Caddy answers from Content-Length alone; Django would wait for the body instead.
    assert send_headers_only(PROXY, 7_000_001) == 413


def test_oversized_body_without_length_gets_no_django_response():
    # Browsers always send Content-Length for uploads; for a chunked body Caddy's request_body
    # cap cuts the stream, which shows up as 413 or a reset connection, never a Django answer.
    body = (b"x" * 65536 for _ in range(128))  # 8 MiB, sent chunked
    try:
        status, _ = fetch(PROXY, "/health/", method="POST", data=body)
    except urllib.error.URLError:
        return
    assert status == 413


def test_body_under_limit_reaches_django():
    status, _ = fetch(PROXY, "/health/", method="POST", data=b"x" * 1024)
    assert status == 403  # Django's CSRF rejection, so the request got past Caddy


# AC-05: Caddy serves static files (Django does not serve them with DEBUG off).
def test_static_files_served_by_caddy():
    status, headers = fetch(PROXY, "/static/admin/css/base.css")
    assert status == 200
    assert headers["Content-Type"].startswith("text/css")


# REQ-MEDIA-002: images through Caddy's forward_auth, with rows in the live database that the
# running web container reads and files in the shared media volume.


@pytest.fixture
def live_image():
    """Create a lesson + image in the live (non-test) database; yield a factory."""
    import io
    import uuid
    from pathlib import Path

    import psycopg
    from PIL import Image

    conn = psycopg.connect(
        host="db",
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        autocommit=True,
    )
    media = Path(os.environ["LIVE_MEDIA_ROOT"])
    created = []

    def one(sql, *params):
        return conn.execute(sql, params).fetchone()[0]

    tag = uuid.uuid4().hex
    user_id = one(
        "INSERT INTO auth_user (password, is_superuser, username, first_name, last_name,"
        " email, is_staff, is_active, date_joined) VALUES ('!', false, %s, '', '', '',"
        " false, true, now()) RETURNING id",
        f"live-{tag}",
    )
    project_id = one(
        "INSERT INTO lessons_project (name, is_active) VALUES (%s, true) RETURNING id",
        f"Live {tag}",
    )
    lookups = {
        "phase_id": one("SELECT id FROM lessons_phase WHERE code = 'CD'"),
        "discipline_id": one("SELECT id FROM lessons_discipline ORDER BY id LIMIT 1"),
        "issue_type_id": one("SELECT id FROM lessons_issuetype ORDER BY id LIMIT 1"),
        "building_component_id": one(
            "SELECT id FROM lessons_buildingcomponent ORDER BY id LIMIT 1"
        ),
    }

    def make(status):
        lesson_id = one(
            "INSERT INTO lessons_lesson (title, description, lesson, project_id, phase_id,"
            " discipline_id, issue_type_id, building_component_id, impact, anonymise,"
            " in_specs, in_standard_details, in_onboarding, status, submitted_by_id,"
            " submitted_at) VALUES ('Live test', 'd', 'l', %s, %s, %s, %s, %s, 'medium',"
            " false, false, false, false, %s, %s, now()) RETURNING id",
            project_id,
            *lookups.values(),
            status,
            user_id,
        )
        name = f"lessons/{uuid.uuid4().hex}.png"
        (media / "lessons").mkdir(mode=0o750, exist_ok=True)
        buffer = io.BytesIO()
        Image.new("RGB", (4, 4), "blue").save(buffer, format="PNG")
        path = media / name
        path.write_bytes(buffer.getvalue())
        path.chmod(0o640)
        conn.execute(
            "INSERT INTO lessons_lessonimage (lesson_id, kind, file, uploaded_at)"
            " VALUES (%s, 'failed', %s, now())",
            (lesson_id, name),
        )
        created.append((lesson_id, path))
        return f"/media/{name}"

    yield make

    for lesson_id, path in created:
        conn.execute("DELETE FROM lessons_lessonimage WHERE lesson_id = %s", (lesson_id,))
        conn.execute("DELETE FROM lessons_lesson WHERE id = %s", (lesson_id,))
        path.unlink(missing_ok=True)
    conn.execute("DELETE FROM lessons_project WHERE id = %s", (project_id,))
    conn.execute("DELETE FROM auth_user WHERE id = %s", (user_id,))
    conn.close()


def test_approved_image_served_through_proxy(live_image):
    status, headers = fetch(PROXY, live_image("approved"))
    assert status == 200
    assert headers["Content-Type"] == "image/png"
    assert headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("status", ["submitted", "rejected"])
def test_unapproved_image_not_served_to_anonymous(live_image, status):
    assert fetch(PROXY, live_image(status))[0] == 404


def test_unknown_media_file_404_through_proxy():
    assert fetch(PROXY, "/media/lessons/00000000000000000000000000000000.png")[0] == 404


def test_internal_endpoints_not_reachable_from_outside(live_image):
    uri = live_image("approved")
    request = urllib.request.Request(
        PROXY + "/internal/media-auth/",
        headers={"Host": os.environ["PORTAL_ADDRESS"], "X-Forwarded-Uri": uri},
    )
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request, timeout=10)
    assert error.value.code == 404


def test_vendored_javascript_served_by_caddy():
    # REQ-KB-001: HTMX comes from our own static files, not a CDN.
    status, headers = fetch(PROXY, "/static/vendor/htmx/htmx-2.0.11.min.js")
    assert status == 200
    assert "javascript" in headers["Content-Type"]
