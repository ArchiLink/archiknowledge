from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from core.audit import audit
from core.roles import QA_GROUP, STAFF_GROUP, is_qa_reviewer
from lessons import review
from lessons.forms import LessonSubmitForm, ReviewForm
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


@require_GET
def my_submissions(request):
    lessons = Lesson.objects.filter(submitted_by=request.user).select_related("project", "phase")
    return render(request, "lessons/my_submissions.html", {"lessons": lessons})


@require_GET
def my_submission_detail(request, pk):
    # Filtered by owner, so another user's lesson is a plain 404 (no hint that it exists).
    lesson = get_object_or_404(
        Lesson.objects.select_related(
            "project", "phase", "discipline", "issue_type", "building_component"
        ).prefetch_related("images"),
        pk=pk,
        submitted_by=request.user,
    )
    return render(request, "lessons/my_submission_detail.html", {"lesson": lesson})


def require_qa(user):
    if not is_qa_reviewer(user):
        raise PermissionDenied


@require_GET
def review_queue(request):
    require_qa(request.user)
    lessons = (
        Lesson.objects.filter(status=Lesson.Status.SUBMITTED)
        .select_related("project", "phase", "submitted_by")
        .order_by("submitted_at")
    )
    return render(request, "lessons/review_queue.html", {"lessons": lessons})


REVIEW_ACTIONS = {"save": None, "approve": review.approve, "reject": review.reject}


@require_http_methods(["GET", "POST"])
def review_lesson(request, pk):
    require_qa(request.user)
    lesson = get_object_or_404(Lesson.objects.prefetch_related("images"), pk=pk)
    was_anonymised = lesson.anonymise
    form = ReviewForm(request.POST or None, instance=lesson)
    if request.method == "POST":
        action = request.POST.get("action")
        if action not in REVIEW_ACTIONS:
            return HttpResponseBadRequest("Unknown action.")
        if form.is_valid():
            with transaction.atomic():
                lesson = form.save()
                if lesson.anonymise != was_anonymised:
                    audit(
                        "anonymise_change",
                        request.user,
                        lesson_id=lesson.pk,
                        anonymise=lesson.anonymise,
                    )
                if REVIEW_ACTIONS[action]:
                    REVIEW_ACTIONS[action](lesson, request.user)
            if action == "save":
                return redirect("review_lesson", pk=lesson.pk)
            return redirect("review_queue")
    return render(request, "lessons/review_lesson.html", {"form": form, "lesson": lesson})
