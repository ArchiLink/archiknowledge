from django.urls import path

from lessons import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("feed/", views.feed, name="feed"),
    path("embed/ticker/", views.embed_ticker, name="embed_ticker"),
    path("knowledge/", views.knowledge_base, name="knowledge_base"),
    path("gallery/", views.gallery, name="gallery"),
    path("lessons/<int:pk>/", views.lesson_detail, name="lesson_detail"),
    path("submit/", views.submit_lesson, name="submit_lesson"),
    path("submit/<int:pk>/done/", views.submit_done, name="submit_done"),
    path("my-submissions/", views.my_submissions, name="my_submissions"),
    path("my-submissions/<int:pk>/", views.my_submission_detail, name="my_submission_detail"),
    path("review/", views.review_queue, name="review_queue"),
    path("review/export.csv", views.export_lessons, name="export_lessons"),
    path("review/<int:pk>/", views.review_lesson, name="review_lesson"),
    path(
        "review/<int:pk>/incorporation/",
        views.update_incorporation,
        name="update_incorporation",
    ),
]
