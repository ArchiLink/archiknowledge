from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from core.audit import audit


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    audit("login", user)


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if user is not None:
        audit("logout", user)


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request=None, **kwargs):
    # Only the username; Django masks the password, but it is never passed on regardless.
    audit("login_failed", username=credentials.get("username", ""))
