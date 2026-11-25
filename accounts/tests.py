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
