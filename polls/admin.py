from django.contrib import admin

from .models import MAX_OPTIONS, Option, Poll


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
