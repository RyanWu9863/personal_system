import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .forms import TaskForm
from .models import ApiToken, Task

def serialize_task(task):
    """把一個 Task 變成可以 JSON 化的字典。"""
    return {
        "id": task.pk,
        "title": task.title,
        "is_done": task.is_done,
        "due_date": task.due_date_isoformat() if task.due_date else None,
        "created_at": task.created_at.isoformat(),
    }

def error(code, message, status, fields=None):
    """統一的錯誤格式。"""
    payload = {"error": {"code": code, "message": message}}
    if fields:
        payload["error"]["fields"] = fields
    return JsonResponse(payload, status=status)

def user_from_token(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    key = header[len("Bearer "):].strip()
    try:
        return ApiToken.objects.get(key=key).user
    except ApiToken.DoesNotExist:
        return None

@csrf_exempt
@require_http_methods(["GET", "POST"])
def task_collection(request):
    user = user_from_token(request)
    if user is None:
        return error("unauthorized", "缺少或無效的 API token", 401)

    if request.method == "GET":
        tasks = Task.objects.filter(owner=user).order_by("is_done", "-created_at")
        return JsonResponse({
            "count": tasks.count(),
            "results": [serialize_task(t) for t in tasks],
        })

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return error("invalid_json", "請求內容不是合法的 JSON", 400)

    form = TaskForm(data, user=user)
    if not form.is_valid():
        return error("validation_error", "資料格式有誤", 400, fields=form.errors)

    task = form.save(commit=False)
    task.owner = user
    task.save()
    return JsonResponse(serialize_task(task), status=201)