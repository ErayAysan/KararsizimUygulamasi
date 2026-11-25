import re
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import User


class UserModelTests(TestCase):
    def test_email_is_lowercased_on_save(self):
        user = User.objects.create_user(username="ahmet", email="Ahmet@Example.COM", password="gucluSifre123")
        self.assertEqual(user.email, "ahmet@example.com")

    def test_username_is_case_insensitive_unique(self):
        User.objects.create_user(username="Ahmet", email="a@example.com", password="gucluSifre123")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username="ahmet", email="b@example.com", password="gucluSifre123")

    def test_email_is_case_insensitive_unique(self):
        User.objects.create_user(username="ahmet", email="a@example.com", password="gucluSifre123")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username="mehmet", email="A@Example.com", password="gucluSifre123")

    def test_invalid_username_rejected(self):
        for bad in ["ab", "a" * 21, "ahmet yilmaz", "ahmet!", "ahmet@"]:
            user = User(username=bad, email=f"{len(bad)}@example.com")
            with self.assertRaises(ValidationError, msg=bad):
                user.full_clean(exclude=["password"])

    def test_valid_username_accepted(self):
        user = User(username="ahmet_y.2", email="ok@example.com")
        user.full_clean(exclude=["password"])


PASSWORD = "gucluSifre123"


def register_data(**overrides):
    data = {
        "username": "ahmet",
        "email": "ahmet@example.com",
        "password1": PASSWORD,
        "password2": PASSWORD,
    }
    data.update(overrides)
    return data


class RegisterTests(TestCase):
    url = reverse("accounts:register")

    def test_page_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kayıt Ol")

    def test_valid_registration_logs_user_in_and_redirects(self):
        response = self.client.post(self.url, register_data(), follow=True)
        self.assertRedirects(response, reverse("polls:list"))
        self.assertTrue(User.objects.filter(username="ahmet").exists())
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertContains(response, "Hoş geldin, @ahmet")

    def test_registration_honors_safe_next(self):
        response = self.client.post(self.url, register_data(next="/admin/"))
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)

    def test_registration_ignores_external_next(self):
        response = self.client.post(self.url, register_data(next="https://evil.example/"))
        self.assertRedirects(response, reverse("polls:list"))

    def test_duplicate_email_rejected_case_insensitive(self):
        User.objects.create_user("mehmet", "ahmet@example.com", PASSWORD)
        response = self.client.post(self.url, register_data(email="AHMET@Example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bu e-posta adresiyle zaten bir hesap var.")
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_username_rejected_case_insensitive(self):
        User.objects.create_user("Ahmet", "baska@example.com", PASSWORD)
        response = self.client.post(self.url, register_data(username="ahmet"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bu kullanıcı adı zaten alınmış.")
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_usernames_rejected(self):
        for bad in ["ab", "a" * 21, "ahmet yilmaz", "ahmet!", "çağrı"]:
            response = self.client.post(self.url, register_data(username=bad))
            self.assertEqual(response.status_code, 200, bad)
            self.assertFalse(User.objects.exists(), bad)

    def test_password_mismatch_rejected(self):
        response = self.client.post(self.url, register_data(password2="baskaSifre456"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_weak_password_rejected(self):
        response = self.client.post(self.url, register_data(password1="123", password2="123"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_email_required(self):
        response = self.client.post(self.url, register_data(email=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_email_saved_lowercase(self):
        self.client.post(self.url, register_data(email="Ahmet@Example.COM"))
        self.assertEqual(User.objects.get().email, "ahmet@example.com")

    def test_authenticated_user_is_redirected_away(self):
        self.client.post(self.url, register_data())
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("polls:list"))


class LoginLogoutTests(TestCase):
    login_url = reverse("accounts:login")
    logout_url = reverse("accounts:logout")

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("ahmet", "ahmet@example.com", PASSWORD)

    def test_login_with_email_and_password(self):
        response = self.client.post(self.login_url, {"username": "ahmet@example.com", "password": PASSWORD}, follow=True)
        self.assertRedirects(response, reverse("polls:list"))
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertContains(response, "Tekrar hoş geldin, @ahmet!")

    def test_login_email_is_case_insensitive(self):
        response = self.client.post(self.login_url, {"username": "AHMET@Example.com", "password": PASSWORD})
        self.assertRedirects(response, reverse("polls:list"))

    def test_login_with_username_is_not_accepted(self):
        response = self.client.post(self.login_url, {"username": "ahmet", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_wrong_password_shows_turkish_error(self):
        response = self.client.post(self.login_url, {"username": "ahmet@example.com", "password": "yanlis"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-posta veya şifre hatalı.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_email_shows_same_error(self):
        response = self.client.post(self.login_url, {"username": "yok@example.com", "password": PASSWORD})
        self.assertContains(response, "E-posta veya şifre hatalı.")

    def test_login_honors_safe_next_and_blocks_external(self):
        data = {"username": "ahmet@example.com", "password": PASSWORD}
        response = self.client.post(self.login_url, {**data, "next": "/admin/"})
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)
        self.client.logout()
        response = self.client.post(self.login_url, {**data, "next": "https://evil.example/"})
        self.assertRedirects(response, reverse("polls:list"))

    def test_logged_in_user_is_redirected_from_login(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(self.login_url), reverse("polls:list"))

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.logout_url).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_via_post(self):
        self.client.force_login(self.user)
        response = self.client.post(self.logout_url, follow=True)
        self.assertRedirects(response, reverse("polls:list"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "Çıkış yaptın.")


class NavbarAndPrivacyTests(TestCase):
    def test_guest_navbar(self):
        response = self.client.get(reverse("polls:list"))
        self.assertContains(response, "Giriş Yap")
        self.assertContains(response, "Kayıt Ol")
        self.assertNotContains(response, "Çıkış")

    def test_member_navbar_shows_username_not_email(self):
        user = User.objects.create_user("ahmet", "gizli@example.com", PASSWORD)
        self.client.force_login(user)
        response = self.client.get(reverse("polls:list"))
        self.assertContains(response, "@ahmet")
        self.assertContains(response, "Çıkış")
        self.assertNotContains(response, "Kayıt Ol")
        self.assertNotContains(response, "gizli@example.com")

    def test_email_not_leaked_on_account_pages(self):
        user = User.objects.create_user("ahmet", "gizli@example.com", PASSWORD)
        self.client.force_login(user)
        for name in ["polls:list"]:
            self.assertNotContains(self.client.get(reverse(name)), "gizli@example.com")


class AdminTests(TestCase):
    def test_superuser_can_open_user_admin_pages(self):
        admin_user = User.objects.create_superuser("yonetici", "yonetici@example.com", PASSWORD)
        self.client.force_login(admin_user)
        for name in ["admin:accounts_user_changelist", "admin:accounts_user_add"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_admin_login_page_is_styled(self):
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)


class EmailFieldLengthTests(TestCase):
    """Uzun e-postalar giriş ve kayıt formlarına sığmalı (maxlength kısıtı olmamalı)."""

    LONG_EMAIL = "bir.cok.uzun.bir.kullanici.adi@ornek-alan-adi.example.com"  # 56 karakter

    def test_login_email_input_has_no_short_maxlength(self):
        html = self.client.get(reverse("accounts:login")).content.decode()
        tag = re.search(r"<input[^>]*name=\"username\"[^>]*>", html).group(0)
        self.assertEqual(re.search(r"maxlength=\"(\d+)\"", tag).group(1), "254")

    def test_register_email_input_allows_long_addresses(self):
        html = self.client.get(reverse("accounts:register")).content.decode()
        tag = re.search(r"<input[^>]*name=\"email\"[^>]*>", html).group(0)
        self.assertGreaterEqual(int(re.search(r"maxlength=\"(\d+)\"", tag).group(1)), len(self.LONG_EMAIL))

    def test_user_with_a_long_email_can_log_in(self):
        User.objects.create_user("uzunmail", self.LONG_EMAIL, PASSWORD)
        response = self.client.post(reverse("accounts:login"), {"username": self.LONG_EMAIL, "password": PASSWORD})
        self.assertRedirects(response, reverse("polls:list"))
