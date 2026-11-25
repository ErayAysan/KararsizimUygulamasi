from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, RegisterForm


def _safe_next_url(request):
    """`next` parametresini yalnızca aynı siteye ait güvenli adreslerde kabul eder."""
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return ""


def register(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    next_url = _safe_next_url(request)
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="accounts.backends.EmailBackend")
        messages.success(request, f"Hoş geldin, @{user.username}! Hesabın oluşturuldu 🎉")
        return redirect(next_url or settings.LOGIN_REDIRECT_URL)

    return render(request, "accounts/register.html", {"form": form, "next": next_url})


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Tekrar hoş geldin, @{form.get_user().username}!")
        return response


class CustomLogoutView(LogoutView):
    """Yalnızca POST ile çıkış yapar (GET → 405)."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, "Çıkış yaptın. Görüşmek üzere! 👋")
        return response
