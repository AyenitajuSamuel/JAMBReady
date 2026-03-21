from django.urls import path
from . import views

urlpatterns = [
    path("", views.recommendations_view, name="recommendations"),
]