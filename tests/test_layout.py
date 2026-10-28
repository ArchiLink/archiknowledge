"""Vendored Pico CSS and the branded base layout (REQ-UI-002)."""

import hashlib
import re
from pathlib import Path

import pytest
from django.contrib.auth.models import Group

from core.roles import QA_GROUP

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
PICO = STATIC / "vendor" / "pico" / "pico-2.1.1.min.css"
THEME = STATIC / "css" / "portal.css"


# AC-01: Pico 2.1.1 is vendored with its licence and recorded hash.


def test_pico_matches_recorded_hash():
    readme = (STATIC / "vendor" / "README.md").read_text(encoding="utf-8")
    row = next(line for line in readme.splitlines() if "pico-2.1.1.min.css" in line)
    recorded = re.search(r"`([0-9a-f]{64})`", row).group(1)
    assert hashlib.sha256(PICO.read_bytes()).hexdigest() == recorded
    assert (STATIC / "vendor" / "pico" / "LICENSE.md").is_file()


# AC-02: every Pico data: icon is overridden by a local SVG file.


def test_every_pico_icon_points_to_a_local_file():
    pico_icons = set(re.findall(r"(--pico-icon-[\w-]+):\s*url\(\"data:", PICO.read_text("utf-8")))
    theme = THEME.read_text(encoding="utf-8")
    overrides = dict(re.findall(r"(--pico-icon-[\w-]+):\s*url\(\"([^\"]+)\"\)", theme))
    assert pico_icons and pico_icons <= overrides.keys()
    for target in overrides.values():
        # Absolute: a relative url() in a variable resolves against Pico's stylesheet, not ours.
        assert target.startswith("/static/"), target
        assert (STATIC / target.removeprefix("/static/")).is_file(), target


def test_theme_and_templates_stay_on_self():
    theme = THEME.read_text(encoding="utf-8")
    assert not re.search(r"url\(\s*[\"']?data:", theme)
    for path in [THEME, *(ROOT / "templates").rglob("*.html")]:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"(src|href)=\"(https?:)?//", text), path
        assert "style=" not in text and "<style" not in text, path


# AC-03: header with logo, navigation (current page marked), account and footer.


def test_layout_has_logo_nav_and_footer(client):
    body = client.get("/").content.decode()
    assert "pico-2.1.1.min.css" in body and "css/portal.css" in body
    assert 'data-theme="light"' in body
    assert 'src="/static/img/architecttura-logo.png" alt="architecttura"' in body
    assert 'class="site-footer"' in body
    assert 'href="/accounts/login/"' in body


@pytest.mark.parametrize(
    ("url", "link"),
    [("/", 'href="/"'), ("/knowledge/", 'href="/knowledge/"'), ("/gallery/", 'href="/gallery/"')],
)
def test_current_page_marked(client, url, link):
    header = client.get(url).content.decode().split("<main")[0]
    assert f'{link} aria-current="page"' in header
    assert header.count('aria-current="page"') == 1


def test_signed_in_header(client, django_user_model):
    user = django_user_model.objects.create_user(username="quinn", password="x" * 12)
    user.groups.add(Group.objects.get(name=QA_GROUP))
    client.force_login(user)
    body = client.get("/review/").content.decode()
    assert "Signed in as <strong>quinn</strong>" in body
    assert 'href="/review/" aria-current="page"' in body
    assert "Sign out" in body and 'href="/accounts/login/"' not in body


def test_no_current_page_outside_the_nav(client):
    assert 'aria-current="page"' not in client.get("/accounts/login/").content.decode()


# AC-04: sign-in and error pages use the layout.


def test_login_page_uses_layout(client):
    body = client.get("/accounts/login/").content.decode()
    assert "architecttura-logo-full.png" in body and 'class="site-header"' in body
    assert "Windows or Microsoft 365 password" in body


def test_404_uses_layout(client):
    response = client.get("/no-such-page/")
    assert response.status_code == 404
    body = response.content.decode()
    assert 'class="site-header"' in body and 'class="error-code">404' in body


def test_500_page_is_styled_but_standalone(client, error_urls):
    client.raise_request_exception = False
    body = client.get("/boom/").content.decode()
    assert "css/portal.css" in body and "architecttura-logo.png" in body
    assert "Something went wrong" in body


# AC-05: the issue template has the UI module code and component.


def test_issue_template_has_ui_module():
    template = (ROOT / ".github" / "ISSUE_TEMPLATE" / "requirement.yml").read_text("utf-8")
    assert "`UI` (site-wide layout and styling)" in template
    assert "- Site-wide layout & styling" in template


# REQ-UI-001 AC-02: every full page uses the theme (partials and emails excluded).


def test_every_page_template_uses_the_theme():
    pages = [
        path
        for path in (ROOT / "templates").rglob("*.html")
        if not path.name.startswith("_") and "emails" not in path.parts
    ]
    assert len(pages) >= 15
    for path in pages:
        text = path.read_text(encoding="utf-8")
        assert '{% extends "base.html" %}' in text or "css/portal.css" in text, path
