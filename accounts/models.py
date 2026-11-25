from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

username_validator = RegexValidator(
    regex=r"^[A-Za-z0-9_.]{3,20}$",
    message="Kullanıcı adı 3-20 karakter olmalı; yalnızca harf, rakam, _ ve . içerebilir.",
)


class User(AbstractUser):
    username = models.CharField(
        "kullanıcı adı",
        max_length=20,
        unique=True,
        validators=[username_validator],
        error_messages={"unique": "Bu kullanıcı adı zaten alınmış."},
    )
    email = models.EmailField(
        "e-posta",
        unique=True,
        error_messages={"unique": "Bu e-posta adresiyle zaten bir hesap var."},
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("username"),
                name="accounts_user_username_ci_unique",
                violation_error_message="Bu kullanıcı adı zaten alınmış.",
            ),
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
                violation_error_message="Bu e-posta adresiyle zaten bir hesap var.",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username
