"""Group names and role checks. Groups are created by core/migrations/0001_create_groups."""

STAFF_GROUP = "Staff"
QA_GROUP = "QA Reviewers"


def is_qa_reviewer(user):
    return user.is_authenticated and user.groups.filter(name=QA_GROUP).exists()
