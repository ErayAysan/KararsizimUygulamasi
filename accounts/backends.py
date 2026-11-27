from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied

from . import throttle


class EmailBackend(ModelBackend):
    """E-posta + şifre ile girişi sağlar (büyük/küçük harf duyarsız).

    ``@`` içermeyen değerler normal kullanıcı adı olarak ele alınır; böylece
    ``createsuperuser`` ile oluşturulan hesaplar admin'e kullanıcı adıyla girebilir.
    Herkese açık giriş formu yalnızca e-posta kabul eder (bkz. ``accounts.forms.LoginForm``).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # Hız sınırı: hem site girişi hem /admin/ buradan geçer. PermissionDenied, Django'nun
        # `authenticate()` işleminde "giriş başarısız" sayılır (doğru şifre olsa bile).
        if username is not None and throttle.is_blocked(request, username):
            raise PermissionDenied
        if username is None or password is None or "@" not in username:
            return super().authenticate(request, username=username, password=password, **kwargs)

        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=username.strip())
        except User.DoesNotExist:
            # Zamanlama farkından kullanıcı varlığı anlaşılmasın.
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
