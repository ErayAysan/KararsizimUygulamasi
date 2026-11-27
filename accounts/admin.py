from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import RegisterForm
from .models import LoginAttempt, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Admin'den kullanıcı eklerken e-posta da zorunlu (benzersizlik kuralı için).
    add_form = RegisterForm
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "password1", "password2")}),
    )
    list_display = ("username", "email", "is_staff", "is_active", "date_joined")
    search_fields = ("username", "email")
    ordering = ("-date_joined",)


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Hız sınırı kayıtları (özetlenmiş anahtarlar); yalnızca görüntülenir/silinir."""

    list_display = ("key", "created_at")
    readonly_fields = ("key", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
