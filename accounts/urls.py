from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("kayit/", views.register, name="register"),
    path("giris/", views.CustomLoginView.as_view(), name="login"),
    path("cikis/", views.CustomLogoutView.as_view(), name="logout"),
]
