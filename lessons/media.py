"""Access check for uploaded images, called by Caddy's forward_auth (REQ-MEDIA-002).

Caddy sends the original request's cookies and its URI in X-Forwarded-Uri. A 2xx answer lets
Caddy serve the file; anything else is passed back to the browser. Unknown files and files the
user may not see get the same 404, so nothing reveals that an unapproved image exists.
"""

from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET

from core.roles import is_qa_reviewer
from lessons.models import Lesson, LessonImage


def can_view_image(user, image):
    lesson = image.lesson
    if lesson.status == Lesson.Status.APPROVED:
        return True
    return user.is_authenticated and (lesson.submitted_by_id == user.pk or is_qa_reviewer(user))


@login_not_required  # anonymous viewers may load images of Approved lessons
@require_GET
def media_auth(request):
    path = unquote(urlsplit(request.headers.get("X-Forwarded-Uri", "")).path)
    if not path.startswith(settings.MEDIA_URL):
        raise Http404
    name = path.removeprefix(settings.MEDIA_URL)
    image = LessonImage.objects.select_related("lesson").filter(file=name).first()
    if image is None or not can_view_image(request.user, image):
        raise Http404
    return HttpResponse(status=204)
