"""Submission and review notifications (REQ-EMAIL-001). Links are permalinks; no images."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from core import email
from core.roles import QA_GROUP
from lessons.models import Lesson


def notify_submitted(lesson, request):
    """Tell QA Reviewers a lesson is waiting, once the submission is committed."""
    reviewers = get_user_model().objects.filter(groups__name=QA_GROUP, is_active=True)
    context = {
        "lesson": lesson,
        "review_url": request.build_absolute_uri(reverse("review_lesson", args=[lesson.pk])),
    }
    transaction.on_commit(
        lambda: email.send(
            "submitted",
            reviewers.values_list("email", flat=True),
            f"New lesson to review: {lesson.title}",
            "emails/submitted.txt",
            context,
        )
    )


def notify_reviewed(lesson, request):
    """Tell the submitter their lesson was approved or rejected."""
    approved = lesson.status == Lesson.Status.APPROVED
    target = (
        reverse("lesson_detail", args=[lesson.pk])
        if approved
        else reverse("my_submission_detail", args=[lesson.pk])
    )
    context = {"lesson": lesson, "approved": approved, "url": request.build_absolute_uri(target)}
    outcome = "approved" if approved else "not approved"
    transaction.on_commit(
        lambda: email.send(
            "approved" if approved else "rejected",
            [lesson.submitted_by.email],
            f"Your lesson was {outcome}: {lesson.title}",
            "emails/reviewed.txt",
            context,
        )
    )
