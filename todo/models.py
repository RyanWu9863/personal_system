from django.conf import settings
from django.db import models
import secrets

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
    
def generate_api_key():
    return secrets.token_hex(20)

class ApiToken(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_token",
    )
    key = models.CharField(max_length=40, unique=True, default=generate_api_key)
    created_at = models.DateTimeField(auto_now_add=True)

    def __int__(self):
        return f"{self.user.username} 的 API token" 