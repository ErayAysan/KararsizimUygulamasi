from django.shortcuts import render


def poll_list(request):
    """Faz 1: yalnızca karşılama sayfası. Anket listesi Faz 3'te gelecek."""
    return render(request, "polls/poll_list.html")
