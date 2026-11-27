"""Giriş denemesi hız sınırı.

Başarısız denemeler iki anahtarla sayılır: hesap (e-posta/kullanıcı adı) ve IP adresi. Pencere
içinde sınır aşılırsa doğru şifre bile geçici olarak reddedilir. Sayaç veritabanında tutulur
(Vercel'de sunucular arası bellek paylaşımı yok). Anahtarlar gizli anahtarla özetlenir; veritabanında
ham e-posta ya da IP bulunmaz.
"""

import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import LoginAttempt

WINDOW = timedelta(minutes=15)
MAX_FAILURES_PER_ACCOUNT = 5
MAX_FAILURES_PER_IP = 20

THROTTLED_MESSAGE = "Çok fazla hatalı giriş denemesi yaptın. Lütfen 15 dakika sonra tekrar dene."


def _digest(kind, value):
    message = f"{kind}:{value}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _account_key(identifier):
    return _digest("hesap", (identifier or "").strip().lower())


def client_ip(request):
    """İstemci IP'si. Vercel `X-Forwarded-For` başlığını gerçek istemci adresiyle yazar."""
    if request is None:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded and not settings.DEBUG:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _keys(request, identifier):
    keys = [(_account_key(identifier), MAX_FAILURES_PER_ACCOUNT)]
    ip = client_ip(request)
    if ip:
        keys.append((_digest("ip", ip), MAX_FAILURES_PER_IP))
    return keys


def is_blocked(request, identifier):
    since = timezone.now() - WINDOW
    for key, limit in _keys(request, identifier):
        if LoginAttempt.objects.filter(key=key, created_at__gte=since).count() >= limit:
            return True
    return False


def record_failure(request, identifier):
    # Süresi dolan kayıtlar her hatada temizlenir; tablo büyümez.
    LoginAttempt.objects.filter(created_at__lt=timezone.now() - WINDOW).delete()
    LoginAttempt.objects.bulk_create([LoginAttempt(key=key) for key, _ in _keys(request, identifier)])


def clear_account(identifier):
    """Başarılı girişte o hesabın sayacı sıfırlanır (IP sayacı kalır)."""
    LoginAttempt.objects.filter(key=_account_key(identifier)).delete()
