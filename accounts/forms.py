from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


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

    error_messages = {
        "invalid_login":"E-posta veya şifre hatalı. Lütfen tekrar dene.",
        "inactive": "Bu hesap devre dışı.",
    }
