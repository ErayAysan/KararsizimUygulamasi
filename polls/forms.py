from datetime import timedelta

from django import forms
from django.db import transaction
from django.utils import timezone

from .models import MAX_OPTIONS, MIN_OPTIONS, Option, Poll

OPTION_MAX_LENGTH = Option._meta.get_field("text").max_length

# Hazır anket süreleri: değer saat cinsindendir; "0" süresiz demektir.
DURATION_CHOICES = [
    ("0", "Süresiz"),
    ("1", "1 saat"),
    ("6", "6 saat"),
    ("24", "1 gün"),
    ("72", "3 gün"),
    ("168", "1 hafta"),
]


class PollForm(forms.Form):
    """Soru + 2-5 seçenek.

    Seçenekler aynı adlı (`option`) birden çok girdi olarak gelir. JavaScript kapalıyken 5 alan
    görünür; boş bırakılanlar yok sayılır. JavaScript açıkken alanlar gösterilip gizlenir.
    """

    question = forms.CharField(
        label="Sorun",
        min_length=5,
        max_length=200,
        strip=True,
        widget=forms.TextInput(attrs={"placeholder": "Örn: Bugün sinemaya mı gitsem, müzeye mi?"}),
        error_messages={
            "required": "Sorunu yazmalısın.",
            "min_length": "Soru en az 5 karakter olmalı.",
            "max_length": "Soru en fazla 200 karakter olabilir.",
        },
    )

    duration = forms.ChoiceField(
        label="Anket süresi",
        choices=DURATION_CHOICES,
        initial="0",
        required=False,
        error_messages={"invalid_choice": "Geçerli bir süre seç."},
    )

    vote_change = forms.ChoiceField(
        label="Oy değiştirme",
        choices=[("0", "Hayır"), ("1", "Evet")],
        initial="0",
        required=False,
        widget=forms.RadioSelect,
        error_messages={"invalid_choice": "Geçerli bir seçenek seç."},
    )

    def __init__(self, data=None, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(data, *args, **kwargs)
        raw = data.getlist("option") if data is not None else []
        # Şablon her zaman MAX_OPTIONS alan çizer; eksikler boş kalır.
        self.option_values = (raw + [""] * MAX_OPTIONS)[:MAX_OPTIONS]
        self._extra_option_count = max(len(raw) - MAX_OPTIONS, 0)
        self.cleaned_options = []

    @property
    def option_fields(self):
        """Şablon için: her seçenek alanının sırası, değeri ve zorunluluğu."""
        return [
            {"index": i, "id": f"id_option_{i}", "value": value, "required": i < MIN_OPTIONS}
            for i, value in enumerate(self.option_values)
        ]

    def clean(self):
        cleaned = super().clean()

        if self._extra_option_count:
            raise forms.ValidationError(f"En fazla {MAX_OPTIONS} seçenek ekleyebilirsin.")

        options = [value.strip() for value in self.option_values]
        options = [value for value in options if value]  # boş bırakılanlar yok sayılır

        if len(options) < MIN_OPTIONS:
            raise forms.ValidationError(f"En az {MIN_OPTIONS} seçenek girmelisin.")

        for text in options:
            if len(text) > OPTION_MAX_LENGTH:
                raise forms.ValidationError(f"Her seçenek en fazla {OPTION_MAX_LENGTH} karakter olabilir.")

        # Büyük/küçük harf duyarsız tekrar kontrolü.
        folded = [text.casefold() for text in options]
        if len(set(folded)) != len(folded):
            raise forms.ValidationError("Aynı seçeneği birden fazla kez yazmışsın.")

        self.cleaned_options = options
        return cleaned

    def save(self, author):
        """Anketi ve seçenekleri tek işlemde (atomik) kaydeder."""
        with transaction.atomic():
            hours = int(self.cleaned_data.get("duration") or 0)
            ends_at = timezone.now() + timedelta(hours=hours) if hours else None
            poll = Poll.objects.create(
                author=author,
                question=self.cleaned_data["question"],
                ends_at=ends_at,
                allow_vote_change=self.cleaned_data.get("vote_change") == "1",
            )
            Option.objects.bulk_create(
                [Option(poll=poll, text=text, order=index) for index, text in enumerate(self.cleaned_options)]
            )
        return poll
