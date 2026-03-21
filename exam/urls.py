from django.urls import path
from . import views

urlpatterns = [
    path("", views.lobby, name="exam_lobby"),
    path("start/", views.start_exam, name="start_exam"),
    path("<int:session_id>/", views.exam_question, name="exam_question"),
    path("<int:session_id>/q/<int:order>/", views.exam_question, name="exam_question"),
    path("<int:session_id>/submit/", views.submit_answer, name="submit_answer"),
    path("<int:session_id>/abandon/", views.abandon_exam, name="abandon_exam"),
    path("<int:session_id>/complete/", views.exam_complete, name="exam_complete"),
    path("history/", views.exam_history, name="exam_history"),
]