from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PollForm
from .models import Poll

POLLS_PER_PAGE = 10


def poll_list(request):
    polls = Poll.objects.select_related("author").annotate(option_count=Count("options")).order_by("-created_at")
    page = Paginator(polls, POLLS_PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "polls/poll_list.html", {"page": page})


def poll_detail(request, public_id):
    poll = get_object_or_404(Poll.objects.select_related("author").prefetch_related("options"), public_id=public_id)
    return render(request, "polls/poll_detail.html", {"poll": poll})


def poll_create(request):
    if not request.user.is_authenticated:
        messages.info(request, "Anket oluşturmak için giriş yapmalısın.")
        return redirect_to_login(request.get_full_path())

    form = PollForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        poll = form.save(author=request.user)
        messages.success(request, "Anketin yayında! 🎉")
        return redirect(poll)

    return render(request, "polls/poll_create.html", {"form": form})
