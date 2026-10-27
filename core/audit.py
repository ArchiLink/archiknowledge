"""Audit log: one line per security or workflow event, written to stdout (SECURITY.md).

Call `audit("event", user, field=value)`. Only the fields in AUDIT_FIELDS are accepted so that
passwords, tokens and request bodies can't be logged by accident. Values are JSON-quoted, so
user-supplied text can't break a line or forge another entry.
"""

import json
import logging

logger = logging.getLogger("portal.audit")

AUDIT_FIELDS = frozenset(
    {
        "action",
        "anonymise",
        "count",
        "lesson_id",
        "object_id",
        "object_type",
        "recipients",
        "status",
        "username",
    }
)


def audit(event, user=None, **fields):
    unknown = fields.keys() - AUDIT_FIELDS
    if unknown:
        raise ValueError(f"Not an audit field: {', '.join(sorted(unknown))}")
    username = user.get_username() if user is not None and user.is_authenticated else "-"
    parts = [f"event={event}", f"user={json.dumps(username)}"]
    parts += [f"{key}={json.dumps(str(value))}" for key, value in sorted(fields.items())]
    logger.info(" ".join(parts))
