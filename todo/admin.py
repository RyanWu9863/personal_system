from django.contrib import admin
from .models import Task

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "is_done", "due_date", "created_at")
    list_filter = ("is_done",)
    search_fields = ("title",)

