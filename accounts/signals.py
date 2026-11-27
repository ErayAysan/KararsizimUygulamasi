from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from . import throttle


@receiver(user_login_failed)
def count_failed_login(sender, credentials, request=None, **kwargs):
    identifier = credentials.get("username")
    if identifier is None:
        return
    # Zaten engelliyse sayaç büyütülmez (engel kendiliğinden kalkabilsin).
    if not throttle.is_blocked(request, identifier):
        throttle.record_failure(request, identifier)


@receiver(user_logged_in)
def reset_login_counter(sender, request, user, **kwargs):
    throttle.clear_account(user.email)
    throttle.clear_account(user.get_username())
