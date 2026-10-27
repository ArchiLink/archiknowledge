import pytest

pytestmark = pytest.mark.django_db


def test_health_returns_ok_without_login(client):
    # REQ-OPS-003 AC-01
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.content == b"ok"


def test_health_rejects_post(client):
    response = client.post("/health/")
    assert response.status_code == 405
