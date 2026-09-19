from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import ApiToken
from .models import Task

import json

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

class TaskApiTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="test-pw-1")
        self.bob = User.objects.create_user(username="bob", password="test-pw-2")
        self.alice_token = ApiToken.objects.create(user=self.alice)
        Task.objects.create(owner=self.bob, title="鮑伯的秘密待辦")
        self.url = reverse("api-tasks")

    def auth(self, token=None):
        """組出 Authorization header；不傳 token 就給一把假的。"""
        key = token.key if token else "not-a-real-token"
        return {"authorization": f"Bearer {key}"}

    def test_missing_token_is_rejected(self):
        """沒有 token 應該回 401。"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "unauthorized")

    def test_invalid_token_is_rejected(self):
        """token 不存在也應該回 401。"""
        response = self.client.get(self.url, headers=self.auth())

        self.assertEqual(response.status_code, 401)

    def test_list_returns_only_own_tasks(self):
        """清單只回 token 主人的待辦。"""
        Task.objects.create(owner=self.alice, title="愛麗絲的待辦")

        response = self.client.get(self.url, headers=self.auth(self.alice_token))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["title"], "愛麗絲的待辦")

    def test_post_creates_task_owned_by_token_user(self):
        """建立的待辦主人要是 token 的持有者。"""
        response = self.client.post(
            self.url,
            data=json.dumps({"title": "從 API 新增"}),
            content_type="application/json",
            headers=self.auth(self.alice_token),
        )

        self.assertEqual(response.status_code, 201)
        task = Task.objects.get(pk=response.json()["id"])
        self.assertEqual(task.owner, self.alice)

    def test_short_title_returns_validation_error(self):
        """標題太短要回 400，並附上欄位錯誤。"""
        response = self.client.post(
            self.url,
            data=json.dumps({"title": "A"}),
            content_type="application/json",
            headers=self.auth(self.alice_token),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.assertIn("title", response.json()["error"]["fields"])
        self.assertEqual(Task.objects.filter(owner=self.alice).count(), 0)

    def test_malformed_json_returns_400(self):
        """內容不是 JSON 要回 400，不是 500。"""
        response = self.client.post(
            self.url,
            data="這不是 JSON",
            content_type="application/json",
            headers=self.auth(self.alice_token),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_json")