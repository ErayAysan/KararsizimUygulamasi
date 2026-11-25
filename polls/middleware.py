import uuid

from django.conf import settings

COOKIE_NAME = "kararsizim_voter"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 yıl


class VoterTokenMiddleware:
    """Her ziyaretçiye imzalı bir çerezle UUID atar (misafir oyları için kimlik).

    - `request.voter_token`: ziyaretçinin UUID'si (çerez yoksa/bozuksa yeni üretilir).
    - `request.voter_token_is_new`: çerez bu istekle birlikte gelmediyse True. Çerezleri
      kapatan biri her istekte yeni kimlik alıp tekrar tekrar oy veremesin diye oy view'u
      bunu kontrol eder.

    Bilinçli kabul (prototip): çerezi silen biri tekrar oy verebilir.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = self._read_token(request)
        request.voter_token_is_new = token is None
        request.voter_token = token or uuid.uuid4()

        response = self.get_response(request)

        if request.voter_token_is_new:
            response.set_signed_cookie(
                COOKIE_NAME,
                str(request.voter_token),
                max_age=COOKIE_MAX_AGE,
                httponly=True,
                samesite="Lax",
                secure=not settings.DEBUG,
            )
        return response

    @staticmethod
    def _read_token(request):
        raw = request.get_signed_cookie(COOKIE_NAME, default=None, max_age=COOKIE_MAX_AGE)
        if not raw:
            return None
        try:
            return uuid.UUID(raw)
        except ValueError:
            return None
