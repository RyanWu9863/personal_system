from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Task

User = get_user_model()

class TaskOwnershipTests(TestCase):
    """驗證資料只屬於它的主人。"""

    def setUp(self):
        # 每一個 test 方法執行前都會重跑一次，拿到乾淨的資料
        self.alice = User.objects.create_user(username='alice', password="test-pw-1")
        self.bob = User.objects.create_user(username="bob", password="test-pw-2")
        self.bob_task = Task.objects.create(owner=self.bob, title="鮑伯的秘密待辦")

    def test_anonymous_is_redirected_to_login(self):
        """未登入開首頁應該被導去登入頁。"""
        response = self.client.get(reverse("todo:list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_list_shows_only_own_tasks(self):
        """清單只顯示自己的待辦，看不到別人的。"""
        self.client.force_login(self.alice)
        Task.objects.create(owner=self.alice, title="愛麗絲的待辦")

        response = self.client.get(reverse("todo:list"))

        self.assertContains(response, "愛麗絲的待辦")
        self.assertNotContains(response, "鮑伯的秘密待辦")

    def test_cannot_delete_someone_elses_task(self):
        """直接打別人資料的網址應該回 404，而且資料要完好。"""
        self.client.force_login(self.alice)

        response = self.client.post(reverse("todo:delete", args=[self.bob_task.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Task.objects.filter(pk=self.bob_task.pk).exists())

class SignupTests(TestCase):
    def test_weak_password_returns_form_not_500(self):
        """密碼太弱時要回傳表單，不是 500。"""
        response = self.client.post(reverse("todo:signup"), {
            "username": "newbie",
            "password1": "123",
            "password2": "123",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newbie").exists())

class TaskFormTests(TestCase):
    def test_short_title_is_rejected(self):
        """標題只有一個字時不該建立資料。"""
        user = User.objects.create_user(username="carol", password="test-pw-3")
        self.client.force_login(user)

        response = self.client.post(reverse("todo:add"), {"title": "A"})

        self.assertEqual(Task.objects.count(), 0)
        self.assertContains(response, "標題至少要 2 個字")