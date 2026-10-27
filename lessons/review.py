"""Review actions: the only code that changes a lesson's status or review audit fields
(SECURITY.md "Set the review audit fields only through the review action")."""

from django.utils import timezone

from core.audit import audit
from lessons.models import Lesson


def approve(lesson, reviewer):
    now = timezone.now()
    if lesson.status != Lesson.Status.APPROVED:
        lesson.approved_at = now  # first publication time; the digest selects on this
    lesson.status = Lesson.Status.APPROVED
    lesson.reviewed_by = reviewer
    lesson.reviewed_at = now
    lesson.save(update_fields=["status", "reviewed_by", "reviewed_at", "approved_at"])
    audit("approval", reviewer, lesson_id=lesson.pk, status=lesson.status)


def reject(lesson, reviewer):
    lesson.status = Lesson.Status.REJECTED
    lesson.reviewed_by = reviewer
    lesson.reviewed_at = timezone.now()
    lesson.approved_at = None  # no longer published
    lesson.save(update_fields=["status", "reviewed_by", "reviewed_at", "approved_at"])
    audit("rejection", reviewer, lesson_id=lesson.pk, status=lesson.status)
