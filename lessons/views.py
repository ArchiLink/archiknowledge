from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from core.audit import audit
from core.roles import QA_GROUP, STAFF_GROUP
from lessons.forms import LessonSubmitForm
from lessons.models import Lesson, LessonImage


def require_staff(user):
    if not user.groups.filter(name__in=[STAFF_GROUP, QA_GROUP]).exists():
        raise PermissionDenied


@require_http_methods(["GET", "POST"])
def submit_lesson(request):
    require_staff(request.user)
    form = LessonSubmitForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        lesson = save_submission(form, request.user)
        audit("submission", request.user, lesson_id=lesson.pk)
        return redirect("submit_done", pk=lesson.pk)
    return render(request, "lessons/submit.html", {"form": form})


def save_submission(form, user):
    """Save the lesson and its images together; remove any written files if it fails."""
    saved = []
    try:
        with transaction.atomic():
            lesson = form.save(commit=False)
            lesson.submitted_by = user
            lesson.save()
            for kind, field in [
                (LessonImage.Kind.FAILED, "failed_images"),
                (LessonImage.Kind.FIXED, "fixed_images"),
            ]:
                for content in form.cleaned_data[field]:
                    image = LessonImage(lesson=lesson, kind=kind)
                    image.file.save(content.name, content, save=False)
                    saved.append(image.file)
                    image.save()
    except Exception:
        for file in saved:
            file.storage.delete(file.name)
        raise
    return lesson


def submit_done(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk, submitted_by=request.user)
    return render(request, "lessons/submit_done.html", {"lesson": lesson})
