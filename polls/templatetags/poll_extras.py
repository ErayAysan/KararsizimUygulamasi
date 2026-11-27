from django import template
from django.utils import timezone
from django.utils.timesince import timesince, timeuntil

register = template.Library()


@register.filter
def since(value):
    """'3 saat önce' gibi; bir dakikadan yeniyse 'az önce'."""
    if not value:
        return ""
    if (timezone.now() - value).total_seconds() < 60:
        return "az önce"
    return f"{timesince(value, depth=1)} önce"


@register.filter
def remaining(value):
    """'3 saat kaldı' gibi; bir dakikadan azsa 'birazdan bitiyor'."""
    if not value:
        return ""
    if (value - timezone.now()).total_seconds() < 60:
        return "birazdan bitiyor"
    return f"{timeuntil(value, depth=1)} kaldı"
