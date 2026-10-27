"""Email the Approved High-impact lessons published since the last digest (REQ-EMAIL-002).

The scheduler runs this weekly with --if-due, which sends only when DIGEST_INTERVAL_DAYS have
passed since the last successful run (cron can't express "every two weeks"). A run is
recorded only when the digest was sent or there was nothing to send, so a skipped or failed
run is retried next time with nothing lost.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from core import email
from lessons.models import DigestRun, Lesson

logger = logging.getLogger("portal.digest")


class Command(BaseCommand):
    help = "Email Approved High-impact lessons published since the last digest."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-due",
            action="store_true",
            help="Do nothing unless DIGEST_INTERVAL_DAYS have passed since the last digest.",
        )

    def handle(self, *args, if_due=False, **options):
        now = timezone.now()
        last = DigestRun.objects.first()
        interval = timedelta(days=settings.DIGEST_INTERVAL_DAYS)
        # Allow an hour of slack so a weekly cron at a fixed time stays on schedule.
        if if_due and last and now - last.run_at < interval - timedelta(hours=1):
            logger.info("digest not due; last run %s", last.run_at.isoformat())
            return

        since = last.run_at if last else now - interval  # first run: the last fortnight only
        lessons = list(
            Lesson.objects.approved()
            .filter(impact=Lesson.Impact.HIGH, approved_at__gt=since, approved_at__lte=now)
            .select_related("project", "phase", "discipline")
            .order_by("approved_at")
        )
        if not lessons:
            logger.info("digest: no new High-impact lessons since %s", since.isoformat())
            DigestRun.objects.create(run_at=now, lesson_count=0)
            return

        base = settings.PORTAL_BASE_URL
        items = [
            {"lesson": lesson, "url": base + reverse("lesson_detail", args=[lesson.pk])}
            for lesson in lessons
        ]
        sent = email.send(
            "digest",
            settings.QUALITY_ALERT_RECIPIENTS,
            f"Quality Alert: {len(lessons)} high-impact lesson{'s' if len(lessons) != 1 else ''}",
            "emails/digest.txt",
            {"items": items, "since": since},
        )
        if sent:
            DigestRun.objects.create(run_at=now, lesson_count=len(lessons))
        else:
            logger.info("digest not sent; window kept from %s for the next run", since.isoformat())
