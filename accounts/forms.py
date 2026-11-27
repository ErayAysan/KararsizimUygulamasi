from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from . import throttle
from .models import User

EMAIL_MAX_LENGTH = User._meta.get_field("email").max_length  # 254


class RegisterForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")
        labels = {"username": "Kullanıcı adı", "email": "E-posta"}
        help_texts = {
            "username": "3-20 karakter; harf, rakam, _ ve . kullanabilirsin.",
            "email": "Herkese açık değildir; sadece giriş için kullanılır.",
        }

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Şifre"
        self.fields["password2"].label = "Şifre (tekrar)"
        self.fields["username"].widget.attrs.update(autocomplete="username", autofocus=True)
        self.fields["email"].widget.attrs.update(autocomplete="email")
        self.fields["email"].required = True

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="E-posta",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}),
    )
    password = forms.CharField(
        label="Şifre",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        # AuthenticationForm, `username` alanının uzunluğunu kullanıcı adı modelinden (20) alır.
        # Burada alan bir e-posta olduğu için sınır EmailField'ın standart uzunluğu olmalı.
        self.fields["username"].max_length = EMAIL_MAX_LENGTH
        self.fields["username"].widget.attrs["maxlength"] = EMAIL_MAX_LENGTH

    error_messages = {
        "invalid_login":"E-posta veya şifre hatalı. Lütfen tekrar dene.",
        "inactive": "Bu hesap devre dışı.",
        "throttled": throttle.THROTTLED_MESSAGE,
    }

    def clean(self):
        username = self.cleaned_data.get("username")
        if username and throttle.is_blocked(self.request, username):
            raise forms.ValidationError(self.error_messages["throttled"], code="throttled")
        return super().clean()
