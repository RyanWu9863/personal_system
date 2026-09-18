from django.conf import settings
from django.db import models

class Task(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
        null=True,
    )

    title = models.CharField("標題", max_length=200)
    is_done = models.BooleanField("已完成", default=False)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)
    due_date = models.DateField("截止日", null=True, blank=True)

    def __str__(self):
        return self.title