from django.urls import path

from lessons import views

urlpatterns = [
    path("submit/", views.submit_lesson, name="submit_lesson"),
    path("submit/<int:pk>/done/", views.submit_done, name="submit_done"),
    path("my-submissions/", views.my_submissions, name="my_submissions"),
    path("my-submissions/<int:pk>/", views.my_submission_detail, name="my_submission_detail"),
    path("review/", views.review_queue, name="review_queue"),
    path("review/<int:pk>/", views.review_lesson, name="review_lesson"),
]
