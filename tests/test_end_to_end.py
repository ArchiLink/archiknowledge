"""End-to-end flow for the v1 epic (REQ-OPS-002): submit → review → publish → digest."""

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.test import Client

from core.roles import QA_GROUP, STAFF_GROUP
from lessons.models import Lesson, Project
from tests.test_review import edit_data
from tests.test_submit import form_data, png

pytestmark = pytest.mark.django_db

PROJECT = "Zephyr Wharf Residences"
TITLE = "Missing parapet flashing"
PUBLIC_PAGES = ["/", "/feed/", "/embed/ticker/", "/knowledge/", "/gallery/"]


def member(django_user_model, username, group):
    user = django_user_model.objects.create_user(username=username, password="x" * 12)
    user.groups.add(Group.objects.get(name=group))
    client = Client()
    client.force_login(user)
    return client


def image_visible(client, image):
    return client.get("/internal/media-auth/", HTTP_X_FORWARDED_URI=image.file.url).status_code


@pytest.fixture
def submitted(django_user_model):
    staff = member(django_user_model, "sam", STAFF_GROUP)
    project = Project.objects.create(name=PROJECT)
    data = form_data(
        project=project.pk, failed_images=[png("before.png")], fixed_images=[png("after.png")]
    )
    assert staff.post("/submit/", data).status_code == 302
    return Lesson.objects.get()


# AC-03: a Submitted lesson and its images are hidden from anonymous users everywhere.


def test_submitted_lesson_hidden_from_anonymous(submitted):
    anonymous = Client()
    images = list(submitted.images.all())
    for url in PUBLIC_PAGES:
        assert TITLE not in anonymous.get(url).content.decode(), url
    # The search box echoes the query, so look for the lesson's link and images instead.
    for url in [*PUBLIC_PAGES, f"/knowledge/?q={TITLE}"]:
        body = anonymous.get(url).content.decode()
        assert f"/lessons/{submitted.pk}/" not in body, url
        assert not any(image.file.url in body for image in images), url
    assert anonymous.get(f"/lessons/{submitted.pk}/").status_code == 404
    for image in images:
        assert image_visible(anonymous, image) == 404


# AC-02: QA anonymises and approves; the lesson is published without the project name
# and goes out in the next digest.


def test_approved_anonymised_lesson_published_everywhere(submitted, django_user_model, settings):
    qa = member(django_user_model, "quinn", QA_GROUP)
    response = qa.post(
        f"/review/{submitted.pk}/", edit_data(submitted, anonymise="on", action="approve")
    )
    assert response.status_code == 302
    submitted.refresh_from_db()
    assert submitted.status == Lesson.Status.APPROVED and submitted.anonymise

    anonymous = Client()
    for url in [*PUBLIC_PAGES, f"/knowledge/?q={TITLE}", f"/lessons/{submitted.pk}/"]:
        body = anonymous.get(url).content.decode()
        assert TITLE in body, url
        assert PROJECT not in body, url
    for image in submitted.images.all():
        assert image_visible(anonymous, image) == 204

    settings.EMAIL_HOST = "smtp.example.test"
    settings.QUALITY_ALERT_RECIPIENTS = ["all-staff@example.test"]
    mail.outbox.clear()
    call_command("send_digest")
    (digest,) = mail.outbox
    assert TITLE in digest.body and PROJECT not in digest.body
