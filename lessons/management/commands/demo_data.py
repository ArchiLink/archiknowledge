"""Load or remove the showcase demo lessons and logins (REQ-OPS-009, REQ-OPS-010).

See lessons/demo.py.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from lessons import demo


class Command(BaseCommand):
    help = "Load demo lessons (and with --logins, demo sign-ins), or remove them with --remove."

    def add_arguments(self, parser):
        parser.add_argument(
            "--remove",
            action="store_true",
            help="Delete the demo lessons, images, projects and users; real data is kept.",
        )
        parser.add_argument(
            "--logins",
            action="store_true",
            help="Also create demo.staff and demo.manager with new random passwords.",
        )

    def handle(self, *args, remove=False, logins=False, **options):
        if remove:
            try:
                count = demo.remove()
            except demo.DemoInUse as error:
                raise CommandError(str(error)) from None
            self.stdout.write(self.style.SUCCESS(f"Removed {count} demo lessons."))
            return
        if demo.is_loaded():
            if not logins:
                raise CommandError("Demo data is already loaded. Run with --remove first.")
        else:
            if settings.EMAIL_HOST:
                # The fortnightly digest would email the High-impact demo lessons to all staff.
                raise CommandError("Email is turned on (EMAIL_HOST is set); demo data not loaded.")
            count = demo.load()
            self.stdout.write(self.style.SUCCESS(f"Loaded {count} demo lessons."))
        if logins:
            self.stdout.write("Demo sign-ins (shown once; run --logins again to reset):")
            for username, password in demo.create_logins().items():
                self.stdout.write(f"  {username:<14} {password}")
            self.stdout.write("For the Admin role, sign in with your own named superuser.")
