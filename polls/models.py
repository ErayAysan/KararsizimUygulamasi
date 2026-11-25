import secrets

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models import Q
from django.urls import reverse

# Karışan karakterler (0/o, 1/l/i) çıkarıldı. 31 harf ve 10 karakterle ~8 x 10^14 olasılık var.
PUBLIC_ID_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
PUBLIC_ID_LENGTH = 10
PUBLIC_ID_MAX_ATTEMPTS = 5

MIN_OPTIONS = 2
MAX_OPTIONS = 5


def generate_public_id():
    """Anket adresinde kullanılan rastgele kod. `random` değil, `secrets` kullanılır."""
    return "".join(secrets.choice(PUBLIC_ID_ALPHABET) for _ in range(PUBLIC_ID_LENGTH))


class Poll(models.Model):
    # `id` yalnızca veritabanı içindir; hiçbir yerde (URL, şablon, JSON) dışarı gösterilmez.
    public_id = models.CharField(max_length=PUBLIC_ID_LENGTH, unique=True, db_index=True, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="polls")
    question = models.CharField("soru", max_length=200)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "anket"
        verbose_name_plural = "anketler"

    def __str__(self):
        return self.question

    def get_absolute_url(self):
        return reverse("polls:detail", args=[self.public_id])

    def save(self, *args, **kwargs):
        """Yeni kayıtta kod üretir. Nadir bir çakışmada yeni kodla en fazla 5 kez dener.

        Kod bir kez üretilir ve asla değişmez (paylaşılan bağlantılar bozulmasın).
        """
        if not self._state.adding:
            return super().save(*args, **kwargs)

        for _ in range(PUBLIC_ID_MAX_ATTEMPTS):
            self.public_id = generate_public_id()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                # Hata gerçekten kod çakışmasından mı geldi? Değilse olduğu gibi yükselt.
                if not Poll.objects.filter(public_id=self.public_id).exists():
                    raise
        raise IntegrityError(f"{PUBLIC_ID_MAX_ATTEMPTS} denemede benzersiz anket kodu üretilemedi.")


class Option(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    text = models.CharField("seçenek", max_length=100)
    order = models.PositiveSmallIntegerField("sıra")  # 0-4; oy formunda radio değeri olarak kullanılır

    class Meta:
        ordering = ["order"]
        verbose_name = "seçenek"
        verbose_name_plural = "seçenekler"
        constraints = [
            models.UniqueConstraint(fields=["poll", "order"], name="polls_option_poll_order_unique"),
            models.CheckConstraint(
                condition=Q(order__gte=0) & Q(order__lt=MAX_OPTIONS),
                name="polls_option_order_range",
            ),
        ]

    def __str__(self):
        return self.text
