"""Giriş denemesi hız sınırı: hesap ve IP başına sınır, sıfırlama, pencere, admin ve gizlilik."""

from datetime import timedelta
from unittest import mock

from django.contrib.auth import authenticate
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import throttle
from .models import LoginAttempt, User

PASSWORD = "gucluSifre123"
THROTTLED = throttle.THROTTLED_MESSAGE

# Çok sayıda giriş denemesi var; yavaş şifre özeti testleri gereksiz uzatmasın.
fast_hashing = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


def make_user(username="ahmet", **extra):
    return User.objects.create_user(username, f"{username}@example.com", PASSWORD, **extra)


def attempt(client, email, password="yanlis-sifre", **extra):
    return client.post(reverse("accounts:login"), {"username": email, "password": password}, **extra)


def fail_n(client, email, count, **extra):
    for _ in range(count):
        attempt(client, email, **extra)


@fast_hashing
class AccountThrottleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()

    def test_wrong_passwords_below_the_limit_are_not_blocked(self):
        fail_n(self.client, "ahmet@example.com", throttle.MAX_FAILURES_PER_ACCOUNT - 1)
        response = attempt(self.client, "ahmet@example.com", PASSWORD)
        self.assertEqual(response.status_code, 302)  # giriş başarılı

    def test_account_is_blocked_after_too_many_failures_even_with_the_right_password(self):
        fail_n(self.client, "ahmet@example.com", throttle.MAX_FAILURES_PER_ACCOUNT)
        response = attempt(self.client, "ahmet@example.com", PASSWORD)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, THROTTLED)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_block_is_case_insensitive_for_the_email(self):
        fail_n(self.client, "AHMET@example.com", throttle.MAX_FAILURES_PER_ACCOUNT)
        response = attempt(self.client, "ahmet@EXAMPLE.com", PASSWORD)
        self.assertContains(response, THROTTLED)

    def test_other_accounts_are_not_affected(self):
        make_user("ayse")
        fail_n(self.client, "ahmet@example.com", throttle.MAX_FAILURES_PER_ACCOUNT)
        response = attempt(Client(), "ayse@example.com", PASSWORD)
        self.assertEqual(response.status_code, 302)

    def test_blocked_attempts_do_not_extend_the_block(self):
        fail_n(self.client, "ahmet@example.com", throttle.MAX_FAILURES_PER_ACCOUNT)
        fail_n(self.client, "ahmet@example.com", 10)  # engelliyken denemeler sayılmaz
        self.assertEqual(LoginAttempt.objects.count(), throttle.MAX_FAILURES_PER_ACCOUNT * 2)  # hesap + ip

    def test_successful_login_resets_the_account_counter(self):
        fail_n(self.client, "ahmet@example.com", throttle.MAX_FAILURES_PER_ACCOUNT - 1)
        attempt(self.client, "ahmet@example.com", PASSWORD)
        self.client.logout()
        fail_n(self.client, "ahmet@example.com", throttle.MAX_FAILURES_PER_ACCOUNT - 1)
        response = attempt(self.client, "ahmet@example.com", PASSWORD)
        self.assertEqual(response.status_code, 302)

    def test_block_expires_after_the_window(self):
        fail_n(self.client, "ahmet@example.com", throttle.MAX_FAILURES_PER_ACCOUNT)
        LoginAttempt.objects.update(created_at=timezone.now() - throttle.WINDOW - timedelta(seconds=1))
        response = attempt(self.client, "ahmet@example.com", PASSWORD)
        self.assertEqual(response.status_code, 302)

    def test_old_attempts_are_purged_on_the_next_failure(self):
        fail_n(self.client, "ahmet@example.com", 2)
        LoginAttempt.objects.update(created_at=timezone.now() - throttle.WINDOW - timedelta(minutes=1))
        attempt(self.client, "ahmet@example.com")
        self.assertEqual(LoginAttempt.objects.count(), 2)  # yalnızca yeni deneme (hesap + ip)

    def test_unknown_email_is_throttled_too(self):
        fail_n(self.client, "yok@example.com", throttle.MAX_FAILURES_PER_ACCOUNT)
        response = attempt(self.client, "yok@example.com", PASSWORD)
        self.assertContains(response, THROTTLED)

    def test_authenticate_itself_refuses_when_blocked(self):
        fail_n(self.client, "ahmet@example.com", throttle.MAX_FAILURES_PER_ACCOUNT)
        self.assertIsNone(authenticate(None, username="ahmet@example.com", password=PASSWORD))


@fast_hashing
class IpThrottleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()

    def test_ip_is_blocked_after_too_many_failures_across_accounts(self):
        for i in range(throttle.MAX_FAILURES_PER_IP):
            attempt(self.client, f"kisi{i}@example.com", HTTP_X_FORWARDED_FOR="203.0.113.7")
        response = attempt(self.client, "ahmet@example.com", PASSWORD, HTTP_X_FORWARDED_FOR="203.0.113.7")
        self.assertContains(response, THROTTLED)

    def test_a_different_ip_is_not_blocked(self):
        for i in range(throttle.MAX_FAILURES_PER_IP):
            attempt(self.client, f"kisi{i}@example.com", HTTP_X_FORWARDED_FOR="203.0.113.7")
        response = attempt(Client(), "ahmet@example.com", PASSWORD, HTTP_X_FORWARDED_FOR="198.51.100.9")
        self.assertEqual(response.status_code, 302)

    def test_only_the_first_forwarded_address_counts(self):
        request = mock.Mock(META={"HTTP_X_FORWARDED_FOR": "203.0.113.7, 10.0.0.1", "REMOTE_ADDR": "10.0.0.1"})
        self.assertEqual(throttle.client_ip(request), "203.0.113.7")

    def test_remote_addr_is_used_without_forwarding_header(self):
        request = mock.Mock(META={"REMOTE_ADDR": "192.0.2.1"})
        self.assertEqual(throttle.client_ip(request), "192.0.2.1")


@fast_hashing
class AdminThrottleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = make_user("yonetici", is_staff=True, is_superuser=True)

    def admin_login(self, client, username, password):
        return client.post(reverse("admin:login"), {"username": username, "password": password, "next": reverse("admin:index")})

    def test_admin_login_is_throttled_too(self):
        client = Client()
        for _ in range(throttle.MAX_FAILURES_PER_ACCOUNT):
            self.admin_login(client, "yonetici", "yanlis-sifre")
        response = self.admin_login(client, "yonetici", PASSWORD)
        self.assertEqual(response.status_code, 200)  # giriş formu yeniden çizildi
        self.assertNotIn("_auth_user_id", client.session)

    def test_admin_login_works_below_the_limit(self):
        client = Client()
        self.admin_login(client, "yonetici", "yanlis-sifre")
        response = self.admin_login(client, "yonetici", PASSWORD)
        self.assertEqual(response.status_code, 302)


@fast_hashing
class PrivacyTests(TestCase):
    def test_database_never_stores_the_raw_email_or_ip(self):
        attempt(self.client, "gizli.kisi@example.com", HTTP_X_FORWARDED_FOR="203.0.113.7")
        stored = " ".join(LoginAttempt.objects.values_list("key", flat=True))
        self.assertEqual(LoginAttempt.objects.count(), 2)
        self.assertNotIn("gizli", stored)
        self.assertNotIn("203.0.113.7", stored)
        for key in LoginAttempt.objects.values_list("key", flat=True):
            self.assertEqual(len(key), 64)

    def test_account_and_ip_keys_differ_for_identical_text(self):
        self.assertNotEqual(throttle._digest("hesap", "x"), throttle._digest("ip", "x"))
