from django.conf import settings

from core.roles import is_qa_reviewer

# Navigation section for each URL name, so base.html can mark the current page.
NAV_SECTIONS = {
    "dashboard": "dashboard",
    "knowledge_base": "knowledge",
    "lesson_detail": "knowledge",
    "gallery": "gallery",
    "submit_lesson": "submit",
    "submit_done": "submit",
    "my_submissions": "mine",
    "my_submission_detail": "mine",
    "review_queue": "review",
    "review_lesson": "review",
}


def portal(request):
    match = getattr(request, "resolver_match", None)
    return {
        "portal_name": settings.PORTAL_NAME,
        "is_qa_reviewer": is_qa_reviewer(request.user) if hasattr(request, "user") else False,
        "nav_section": NAV_SECTIONS.get(match.url_name) if match else None,
    }
