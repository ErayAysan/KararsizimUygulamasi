from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import PollForm
from .models import Poll, Vote

POLLS_PER_PAGE = 10


def _voter(request):
    """Oy veren kişiyi tanımlar: üye ise kullanıcı, misafir ise imzalı çerezdeki UUID."""
    if request.user.is_authenticated:
        return {"user": request.user}
    return {"voter_token": request.voter_token}


def poll_list(request):
    # İki sekme: "aktif" (süresi devam eden ve süresiz) ve "bitti" (süresi dolan).
    status = "bitti" if request.GET.get("durum") == "bitti" else "aktif"
    polls = Poll.objects.closed() if status == "bitti" else Poll.objects.active()
    polls = (
        polls.select_related("author")
        # İki ayrı ilişki aynı sorguda sayıldığı için distinct şart (aksi hâlde çarpılırlar).
        .annotate(option_count=Count("options", distinct=True), vote_count=Count("votes", distinct=True))
        .order_by("-ends_at" if status == "bitti" else "-created_at")
    )
    page = Paginator(polls, POLLS_PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "polls/poll_list.html", {"page": page, "status": status})


def _percent(count, total):
    """Tam sayıya yarıdan yukarı yuvarlanmış yüzde (Python'un banker yuvarlamasından kaçınır)."""
    return (count * 100 + total // 2) // total if total else 0


def _rank_step(count, low, high):
    """En çok oy alan 4 (yeşil), en az oy alan 0 (kırmızı); aradakiler orantılı. Eşitlikte hepsi yeşil."""
    span = high - low
    return 4 if span == 0 else ((count - low) * 4 + span // 2) // span


def poll_detail(request, public_id):
    poll = get_object_or_404(Poll.objects.select_related("author"), public_id=public_id)

    options = list(poll.options.annotate(vote_count=Count("votes")))  # Meta.ordering: order
    total_votes = sum(option.vote_count for option in options)

    my_order = (
        Vote.objects.filter(poll=poll, **_voter(request)).values_list("option__order", flat=True).first()
    )
    is_author = request.user.is_authenticated and poll.author_id == request.user.id

    is_closed = poll.is_closed
    # Sonuçlar yalnızca oy vermiş kişiye ve anket sahibine gösterilir (sonuçlar oyları etkilemesin);
    # süresi dolan anketin sonuçları artık oyları etkilemeyeceği için herkese açılır.
    show_results = is_closed or my_order is not None or is_author
    top = max((option.vote_count for option in options), default=0)
    low = min((option.vote_count for option in options), default=0)
    for option in options:
        option.percent = _percent(option.vote_count, total_votes)
        option.is_mine = option.order == my_order
        option.is_winner = top > 0 and option.vote_count == top
        # Süresi dolan ankette çubuklar yeşilden (çok oy) kırmızıya (az oy) boyanır.
        option.rank = _rank_step(option.vote_count, low, top) if is_closed and total_votes else None

    context = {
        "poll": poll,
        "options": options,
        "total_votes": total_votes,
        "show_results": show_results,
        "can_vote": not is_closed and my_order is None,
        "is_closed": is_closed,
    }
    return render(request, "polls/poll_detail.html", context)


@require_POST
def vote(request, public_id):
    poll = get_object_or_404(Poll, public_id=public_id)

    if poll.is_closed:
        messages.warning(request, "Bu anketin süresi doldu, artık oy verilemiyor.")
        return redirect(poll)

    # Çerezler kapalıysa her istekte yeni kimlik üretilir; bu, sınırsız oya yol açar. Reddet.
    if not request.user.is_authenticated and request.voter_token_is_new:
        messages.error(request, "Oy verebilmek için tarayıcında çerezlere izin vermelisin.")
        return redirect(poll)

    # Seçenek, sayısal id ile değil `order` değeriyle bulunur; yalnızca bu anketin seçenekleri aranır.
    try:
        order = int(request.POST.get("option", ""))
    except ValueError:
        order = None
    option = poll.options.filter(order=order).first() if order is not None else None
    if option is None:
        messages.error(request, "Lütfen bir seçenek seç.")
        return redirect(poll)

    voter = _voter(request)
    if Vote.objects.filter(poll=poll, **voter).exists():
        messages.warning(request, "Bu ankete zaten oy verdin.")
        return redirect(poll)

    try:
        with transaction.atomic():
            Vote.objects.create(poll=poll, option=option, **voter)
    except IntegrityError:
        # Aynı anda gelen ikinci istek: veritabanı kısıtı ikinci oyu engeller.
        messages.warning(request, "Bu ankete zaten oy verdin.")
        return redirect(poll)

    messages.success(request, "Oyun kaydedildi! 🎉")
    return redirect(poll)


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
