from django.contrib import admin
from .models import Task
from .models import Task, ApiToken

admin.site.register(ApiToken)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "is_done", "due_date", "created_at")
    list_filter = ("is_done",)
    search_fields = ("title",)

