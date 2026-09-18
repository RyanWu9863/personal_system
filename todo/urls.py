from django.urls import path
from . import views

app_name = "todo"

urlpatterns = [
    path("", views.task_list, name="list"),
    path("signup/", views.signup, name="signup"),
    path("add/", views.task_add, name="add"),
    path("<int:pk>/toggle/", views.task_toggle, name="toggle"),
    path("<int:pk>/delete/", views.task_delete, name="delete"),
]