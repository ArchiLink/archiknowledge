"""Generic error pages (REQ-OPS-005 AC-03, AC-04)."""

import logging

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def error_urls(settings):
    settings.ROOT_URLCONF = "tests.error_urls"
    settings.DEBUG = False


def test_500_is_generic_and_traceback_is_logged(client, error_urls, caplog):
    client.raise_request_exception = False
    with caplog.at_level(logging.ERROR):
        response = client.get("/boom/")
    assert response.status_code == 500
    body = response.content.decode()
    assert "Something went wrong" in body
    assert "boom-test-exception" not in body
    assert "Traceback" not in body
    logged = [r for r in caplog.records if r.exc_info]
    assert any("boom-test-exception" in str(r.exc_info[1]) for r in logged)


def test_403_is_generic(client, error_urls):
    response = client.get("/forbidden/")
    assert response.status_code == 403
    assert "Access denied" in response.content.decode()


def test_404_is_generic(client):
    response = client.get("/no-such-page/")
    assert response.status_code == 404
    body = response.content.decode()
    assert "Page not found" in body
    assert "no-such-page" not in body  # the requested path is not echoed back
