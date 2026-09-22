from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from .models import Task

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "due_date"]
        labels = {"title": "標題", "due_date": "截止日"}
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "要做什麼？",
            }),
            "due_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date",
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 2:
            raise forms.ValidationError("標題至少要 2 個字")

        qs = Task.objects.filter(title=title, is_done=False)
        if self.user is not None:
            qs = qs.filter(owner=self.user)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("已經有一筆一樣的待辦還沒完成")       
        return title
    
class TaskApiForm(TaskForm):
    class Meta(TaskForm.Meta):
        fields = ["title", "due_date", "is_done"]

class BootstrapFormMixin:
    """把 Bootstrap 的 form-control 套到表單的每個欄位上。

    Django 內建的認證表單不帶任何 CSS class，逐一在模板裡加會很囉唆，
    這裡統一處理，登入、註冊、重設密碼三張表單長得才會一致。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} form-control".strip()


class StyledAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    pass


class StyledPasswordResetForm(BootstrapFormMixin, PasswordResetForm):
    pass


class StyledSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass


class SignupForm(BootstrapFormMixin, UserCreationForm):
    """註冊表單，比 Django 內建的多收一個 email。

    沒有 email 就收不到重設密碼的連結，所以這裡設為必填。
    """

    email = forms.EmailField(
        label="電子郵件",
        required=True,
        help_text="忘記密碼時，重設連結會寄到這裡",
    )

    class Meta(UserCreationForm.Meta):
        fields = ["username", "email"]
