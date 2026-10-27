"""Outbound email (SECURITY.md "Input validation" and "Logging").

Plain text only, so user text can't become markup. Sending is skipped, with one log line,
while EMAIL_HOST is empty. A failed send is logged and never breaks the request that caused it.
Log lines carry the email type and recipient count, never addresses or the body.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger("portal.email")


def one_line(text):
    """Subjects can't contain line breaks (header injection)."""
    return " ".join(str(text).split())


def send(kind, recipients, subject, template, context):
    """Send a plain-text email; return the number of recipients it went to."""
    recipients = sorted({address for address in recipients if address})
    if not settings.EMAIL_HOST:
        logger.info(
            "email skipped type=%s recipients=%d reason=no EMAIL_HOST", kind, len(recipients)
        )
        return 0
    if not recipients:
        logger.info("email skipped type=%s recipients=0 reason=no addresses", kind)
        return 0
    body = render_to_string(template, {"portal_name": settings.PORTAL_NAME, **context})
    try:
        send_mail(one_line(subject), body, None, recipients)
    except Exception as error:  # noqa: BLE001 - any SMTP problem is logged, never raised
        logger.error(
            "email failed type=%s recipients=%d error=%s",
            kind,
            len(recipients),
            type(error).__name__,
        )
        return 0
    logger.info("email sent type=%s recipients=%d", kind, len(recipients))
    return len(recipients)
