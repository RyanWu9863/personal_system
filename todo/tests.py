import re
from smtplib import SMTPException
from unittest.mock import patch
from datetime import date

from django.contrib.auth import get_user_model
from django.core import mail
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

    def test_email_is_required(self):
        """沒填 email 就不能註冊，否則之後無法重設密碼。"""
        response = self.client.post(reverse("todo:signup"), {
            "username": "newbie",
            "password1": "a-good-password-42",
            "password2": "a-good-password-42",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newbie").exists())

    def test_signup_saves_the_email(self):
        """註冊填的 email 要真的存進去。"""
        self.client.post(reverse("todo:signup"), {
            "username": "newbie",
            "email": "newbie@example.com",
            "password1": "a-good-password-42",
            "password2": "a-good-password-42",
        })

        self.assertEqual(
            User.objects.get(username="newbie").email, "newbie@example.com"
        )

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

class TaskDetailApiTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="test-pw-1")
        self.bob = User.objects.create_user(username="bob", password="test-pw-2")
        self.token = ApiToken.objects.create(user=self.alice)
        self.task = Task.objects.create(owner=self.alice, title="寫作業")
        self.bob_task = Task.objects.create(owner=self.bob, title="鮑伯的待辦")
        self.headers = {"authorization": f"Bearer {self.token.key}"}

    def url(self, task):
        return reverse("api-task-detail", args=[task.pk])

    def test_get_single_task(self):
        """讀得到自己的單筆待辦。"""
        response = self.client.get(self.url(self.task), headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "寫作業")

    def test_due_date_is_serialized_as_iso_string(self):
        """有截止日的待辦要讀得到，日期格式是 YYYY-MM-DD。"""
        self.task.due_date = date(2026, 1, 31)
        self.task.save()

        response = self.client.get(self.url(self.task), headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["due_date"], "2026-01-31")

    def test_cannot_read_others_task(self):
        """讀別人的要回 JSON 格式的 404。"""
        response = self.client.get(self.url(self.bob_task), headers=self.headers)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_patch_only_is_done_keeps_title(self):
        """只送 is_done，標題不能被清掉。"""
        response = self.client.patch(
            self.url(self.task),
            data=json.dumps({"is_done": True}),
            content_type="application/json",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_done)
        self.assertEqual(self.task.title, "寫作業")

    def test_patch_with_unchanged_title_is_allowed(self):
        """標題原封不動送回來，不該被自己的重複檢查擋下。"""
        response = self.client.patch(
            self.url(self.task),
            data=json.dumps({"title": "寫作業"}),
            content_type="application/json",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)

    def test_delete_returns_204(self):
        """刪除回 204，資料真的消失。"""
        response = self.client.delete(self.url(self.task), headers=self.headers)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())
class ApiTokenPageTests(TestCase):
    """使用者自助產生 API token 的頁面。"""

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="test-pw-1")
        self.page = reverse("todo:api_token")
        self.regenerate = reverse("todo:api_token_regenerate")

    def test_anonymous_is_redirected_to_login(self):
        """未登入不能看 token 頁。"""
        response = self.client.get(self.page)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_page_does_not_create_token_by_itself(self):
        """只是開頁面不該憑空生出 token。"""
        self.client.force_login(self.alice)

        response = self.client.get(self.page)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ApiToken.objects.filter(user=self.alice).exists())

    def test_post_creates_token(self):
        """按下產生後才會有 token。"""
        self.client.force_login(self.alice)

        response = self.client.post(self.regenerate)

        self.assertRedirects(response, self.page)
        self.assertTrue(ApiToken.objects.filter(user=self.alice).exists())

    def test_regenerate_replaces_the_old_key(self):
        """重新產生會換一把新的，不是再開一筆。"""
        self.client.force_login(self.alice)
        self.client.post(self.regenerate)
        old_key = ApiToken.objects.get(user=self.alice).key

        self.client.post(self.regenerate)

        self.assertEqual(ApiToken.objects.filter(user=self.alice).count(), 1)
        self.assertNotEqual(ApiToken.objects.get(user=self.alice).key, old_key)

    def test_old_key_stops_working_after_regenerate(self):
        """輪替之後，舊 key 打 API 要被擋下來。"""
        self.client.force_login(self.alice)
        self.client.post(self.regenerate)
        old_key = ApiToken.objects.get(user=self.alice).key
        self.client.post(self.regenerate)

        response = self.client.get(
            reverse("api-tasks"), headers={"authorization": f"Bearer {old_key}"}
        )

        self.assertEqual(response.status_code, 401)

    def test_regenerate_rejects_get(self):
        """輪替只接受 POST，用 GET 打要被擋。"""
        self.client.force_login(self.alice)

        response = self.client.get(self.regenerate)

        self.assertEqual(response.status_code, 405)
        self.assertFalse(ApiToken.objects.filter(user=self.alice).exists())

    def test_page_shows_own_token_but_not_others(self):
        """頁面顯示自己的 token，看不到別人的。"""
        bob = User.objects.create_user(username="bob", password="test-pw-2")
        bob_token = ApiToken.objects.create(user=bob)
        alice_token = ApiToken.objects.create(user=self.alice)
        self.client.force_login(self.alice)

        response = self.client.get(self.page)

        self.assertContains(response, alice_token.key)
        self.assertNotContains(response, bob_token.key)

    def test_curl_example_is_a_single_line(self):
        """用法範例不能用反斜線續行，否則在 PowerShell 貼上會失敗。"""
        ApiToken.objects.create(user=self.alice)
        self.client.force_login(self.alice)

        response = self.client.get(self.page)

        blocks = response.content.decode().split("<code>")[1:]
        example = next(b.split("</code>")[0] for b in blocks if "curl -H" in b)
        self.assertNotIn("\\", example)

    def test_token_is_hidden_by_default(self):
        """token 欄位預設要是遮住的，不能一進頁面就裸奔。"""
        ApiToken.objects.create(user=self.alice)
        self.client.force_login(self.alice)

        response = self.client.get(self.page)

        self.assertContains(response, 'type="password" id="token-field"')

    def test_usage_example_does_not_contain_the_key(self):
        """用法範例要用佔位符，不能把真的 token 印在上面。"""
        token = ApiToken.objects.create(user=self.alice)
        self.client.force_login(self.alice)

        response = self.client.get(self.page)

        blocks = response.content.decode().split("<code>")[1:]
        example = next(b.split("</code>")[0] for b in blocks if "curl -H" in b)
        self.assertIn("$TOKEN", example)
        self.assertNotIn(token.key, example)


class NavigationTests(TestCase):
    """導覽列該給誰看什麼。"""

    def setUp(self):
        self.url = reverse("todo:list")

    def test_admin_link_is_hidden_from_normal_users(self):
        """一般使用者不該看到後台連結。"""
        user = User.objects.create_user(username="alice", password="test-pw-1")
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertNotContains(response, "後台")

    def test_admin_link_is_shown_to_staff(self):
        """管理員才看得到後台連結。"""
        staff = User.objects.create_user(
            username="boss", password="test-pw-2", is_staff=True
        )
        self.client.force_login(staff)

        response = self.client.get(self.url)

        self.assertContains(response, "後台")


class SettingsPageTests(TestCase):
    def setUp(self):
        self.url = reverse("todo:settings")

    def test_anonymous_is_redirected_to_login(self):
        """未登入看不到設定頁。"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_links_to_api_token_page(self):
        """設定頁要有進入 API token 的入口。"""
        user = User.objects.create_user(username="alice", password="test-pw-1")
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertContains(response, reverse("todo:api_token"))


class LoginPageTests(TestCase):
    def setUp(self):
        self.url = reverse("login")
        User.objects.create_user(username="alice", password="test-pw-1")

    def test_wrong_password_shows_error_in_red_alert(self):
        """帳密錯誤時，訊息要放在紅色警示框裡。"""
        response = self.client.post(
            self.url, {"username": "alice", "password": "wrong-pw"}
        )

        self.assertEqual(response.status_code, 200)
        error = response.context["form"].non_field_errors()[0]
        self.assertContains(response, "alert-danger")
        self.assertContains(response, error)

    def test_page_links_to_password_reset(self):
        """登入頁要有忘記密碼的入口。"""
        response = self.client.get(self.url)

        self.assertContains(response, reverse("password_reset"))


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password="old-pw-12345"
        )

    def test_reset_email_is_sent_to_a_registered_address(self):
        """信箱有註冊過就會收到重設信。"""
        response = self.client.post(
            reverse("password_reset"), {"email": "alice@example.com"}
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("alice@example.com", mail.outbox[0].to)

    def test_unknown_email_sends_nothing_but_looks_the_same(self):
        """沒註冊過的信箱不寄信，但畫面一樣，避免洩漏誰有帳號。"""
        response = self.client.post(
            reverse("password_reset"), {"email": "nobody@example.com"}
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_link_in_email_can_actually_change_the_password(self):
        """照著信裡的連結走完，密碼真的會換掉。"""
        self.client.post(reverse("password_reset"), {"email": "alice@example.com"})
        path = re.search(r"/accounts/reset/[^/]+/[^/\s]+/", mail.outbox[0].body).group()

        form_page = self.client.get(path, follow=True)
        response = self.client.post(
            form_page.request["PATH_INFO"],
            {"new_password1": "brand-new-pw-99", "new_password2": "brand-new-pw-99"},
        )

        self.assertRedirects(response, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("brand-new-pw-99"))

    def test_used_link_stops_working(self):
        """同一個連結用過就不能再用。"""
        self.client.post(reverse("password_reset"), {"email": "alice@example.com"})
        path = re.search(r"/accounts/reset/[^/]+/[^/\s]+/", mail.outbox[0].body).group()
        form_page = self.client.get(path, follow=True)
        self.client.post(
            form_page.request["PATH_INFO"],
            {"new_password1": "brand-new-pw-99", "new_password2": "brand-new-pw-99"},
        )

        response = self.client.get(path, follow=True)

        self.assertFalse(response.context["validlink"])

    def test_reset_pages_use_the_site_layout(self):
        """四個重設頁都要用站內版型。

        Django 後台自己帶了同名的 registration/password_reset_*.html，
        且 django.contrib.admin 排在 todo 前面，放在 app 層會被蓋掉。
        """
        self.client.post(reverse("password_reset"), {"email": "alice@example.com"})
        path = re.search(r"/accounts/reset/[^/]+/[^/\s]+/", mail.outbox[0].body).group()

        pages = [
            self.client.get(reverse("password_reset")),
            self.client.get(reverse("password_reset_done")),
            self.client.get(path, follow=True),
            self.client.get(reverse("password_reset_complete")),
        ]

        for page in pages:
            self.assertContains(page, "我的待辦清單")
            self.assertNotContains(page, "Django 網站管理")

    @patch("django.contrib.auth.forms.PasswordResetForm.save", side_effect=SMTPException)
    def test_mail_failure_shows_an_error_instead_of_500(self, _):
        """寄信失敗要回到表單顯示錯誤，不能讓使用者看到 500。"""
        response = self.client.post(
            reverse("password_reset"), {"email": "alice@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alert-danger")
        self.assertContains(response, "目前無法寄出重設信")
