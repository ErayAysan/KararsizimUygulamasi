from django.urls import path, register_converter

from . import views
from .converters import PublicIdConverter

register_converter(PublicIdConverter, "public_id")

app_name = "polls"

urlpatterns = [
    path("", views.poll_list, name="list"),
    # "yeni/" kodlu yoldan ÖNCE tanımlanır (10 karakter olmadığı için çakışmaz, yine de sıra korunur).
    path("anket/yeni/", views.poll_create, name="create"),
    path("anket/<public_id:public_id>/", views.poll_detail, name="detail"),
    path("anket/<public_id:public_id>/oy/", views.vote, name="vote"),
]
