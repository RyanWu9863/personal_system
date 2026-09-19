from django import forms
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