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
