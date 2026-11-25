from django.contrib import admin

from .models import MAX_OPTIONS, Option, Poll, Vote


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0
    max_num = MAX_OPTIONS
    ordering = ("order",)


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("question", "author", "public_id", "created_at")
    list_select_related = ("author",)
    search_fields = ("question", "public_id", "author__username")
    readonly_fields = ("public_id", "created_at")
    fields = ("public_id", "author", "question", "created_at")
    inlines = [OptionInline]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    """Oylar yalnızca incelenir/silinir (moderasyon); elle oy eklenip değiştirilmez."""

    list_display = ("poll", "option", "user", "voter_token", "created_at")
    list_select_related = ("poll", "option", "user")
    search_fields = ("poll__public_id", "poll__question", "user__username")
    readonly_fields = ("poll", "option", "user", "voter_token", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
