from .models import PUBLIC_ID_LENGTH


class PublicIdConverter:
    """`/anket/<public_id>/` için: yalnızca anket kodu desenine uyan değerleri kabul eder.

    Desene uymayan her şey (sayısal adresler, büyük harf, yanlış uzunluk, 0/o/1/l/i gibi
    alfabede olmayan karakterler) doğrudan 404 olur.
    """

    regex = r"[23456789a-hjkmnp-z]{%d}" % PUBLIC_ID_LENGTH

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value
