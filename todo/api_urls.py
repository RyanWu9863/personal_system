from django.urls import path
from . import api

urlpatterns = [
    path("tasks/", api.task_collection, name="api-tasks"),
    path("tasks/<int:pk>/", api.task_detail, name="api-task-detail"),
]