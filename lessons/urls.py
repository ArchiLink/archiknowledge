from django.urls import path

from lessons import views

urlpatterns = [
    path("submit/", views.submit_lesson, name="submit_lesson"),
    path("submit/<int:pk>/done/", views.submit_done, name="submit_done"),
]
