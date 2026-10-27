from django.conf import settings

from core.roles import is_qa_reviewer


def portal(request):
    return {
        "portal_name": settings.PORTAL_NAME,
        "is_qa_reviewer": is_qa_reviewer(request.user) if hasattr(request, "user") else False,
    }
