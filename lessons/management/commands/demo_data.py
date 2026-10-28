"""Load or remove the showcase demo lessons (REQ-OPS-009). See lessons/demo.py."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from lessons import demo


class Command(BaseCommand):
    help = "Load about a dozen demo lessons for showcasing, or remove them with --remove."

    def add_arguments(self, parser):
        parser.add_argument(
            "--remove",
            action="store_true",
            help="Delete the demo lessons, images, projects and users; real data is kept.",
        )

    def handle(self, *args, remove=False, **options):
        if remove:
            count = demo.remove()
            self.stdout.write(self.style.SUCCESS(f"Removed {count} demo lessons."))
            return
        if settings.EMAIL_HOST:
            # The fortnightly digest would email the High-impact demo lessons to all staff.
            raise CommandError("Email is turned on (EMAIL_HOST is set); demo data not loaded.")
        if demo.is_loaded():
            raise CommandError("Demo data is already loaded. Run with --remove first.")
        count = demo.load()
        self.stdout.write(self.style.SUCCESS(f"Loaded {count} demo lessons."))
