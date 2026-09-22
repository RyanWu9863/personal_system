from django.shortcuts import render ,redirect, get_object_or_404
from .models import ApiToken, Task, generate_api_key
from .forms import SignupForm, TaskForm
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect("todo:list")
    else:
        form = SignupForm()

    # 不論是 GET，還是 POST 但驗證失敗，都要把表單重新畫出來
    return render(request, "registration/signup.html", {"form": form})

@login_required
def task_list(request, form=None):
    tasks = Task.objects.filter(owner=request.user).order_by("is_done", "-created_at")
    return render(request, "todo/list.html", {
        "tasks": tasks,
        "form": form or TaskForm(user=request.user),
    })

@login_required
def task_add(request):
    if request.method != "POST":
        return redirect("todo:list")
    
    form = TaskForm(request.POST, user=request.user)
    if form.is_valid():
        task = form.save(commit=False)
        task.owner = request.user
        task.save()
        return redirect("todo:list")
    
    return task_list(request, form=form)

@login_required
def task_toggle(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    task.is_done = not task.is_done
    task.save()
    return redirect("todo:list")

@login_required
def task_delete(request, pk):
    get_object_or_404(Task, pk=pk, owner=request.user).delete()
    return redirect("todo:list")

@login_required
def api_token(request):
    """顯示自己的 API token；還沒有就顯示產生按鈕。"""
    return render(request, "todo/api_token.html", {
        "token": ApiToken.objects.filter(user=request.user).first(),
    })

@login_required
@require_POST
def api_token_regenerate(request):
    """產生或重新產生 token。舊的 key 會立刻失效。"""
    token, created = ApiToken.objects.get_or_create(user=request.user)
    if not created:
        token.key = generate_api_key()
        token.save()
    return redirect("todo:api_token")

@login_required
def settings_page(request):
    """設定頁：目前只有 API token 一項，之後要加別的都放這裡。"""
    return render(request, "todo/settings.html")
