"""Faz 4: oylama, misafir kimliği (voter token) ve sonuç görünürlüğü testleri."""

import uuid
from unittest import mock

from django.contrib.messages import get_messages
from django.db import IntegrityError, connection
from django.http import HttpResponse
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import User

from .middleware import COOKIE_MAX_AGE, COOKIE_NAME
from .models import Option, Poll, Vote
from .tests import PASSWORD, make_poll, make_user
from .views import _percent


def cast(poll, order, user=None, token=None):
    """Veritabanına doğrudan oy yazar (görünüm testleri için hazırlık)."""
    option = poll.options.get(order=order)
    if user is None and token is None:
        token = uuid.uuid4()
    return Vote.objects.create(poll=poll, option=option, user=user, voter_token=None if user else token)


def messages_of(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


def visit(client, poll):
    """Ziyaretçi sayfayı açar (çerez bu sırada atanır)."""
    return client.get(poll.get_absolute_url())


class VoteModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.poll = make_poll(cls.user, options=("A", "B", "C"))

    def test_member_and_guest_votes_are_valid(self):
        cast(self.poll, 0, user=self.user)
        cast(self.poll, 1, token=uuid.uuid4())
        self.assertEqual(Vote.objects.count(), 2)

    def test_exactly_one_of_user_or_token_is_required(self):
        option = self.poll.options.get(order=0)
        with self.assertRaises(IntegrityError):
            Vote.objects.create(poll=self.poll, option=option, user=self.user, voter_token=uuid.uuid4())

    def test_neither_user_nor_token_is_rejected(self):
        option = self.poll.options.get(order=0)
        with self.assertRaises(IntegrityError):
            Vote.objects.create(poll=self.poll, option=option)

    def test_member_cannot_vote_twice_on_same_poll(self):
        cast(self.poll, 0, user=self.user)
        with self.assertRaises(IntegrityError):
            cast(self.poll, 1, user=self.user)

    def test_guest_cannot_vote_twice_on_same_poll(self):
        token = uuid.uuid4()
        cast(self.poll, 0, token=token)
        with self.assertRaises(IntegrityError):
            cast(self.poll, 1, token=token)

    def test_same_person_can_vote_on_different_polls(self):
        other = make_poll(self.user, question="Başka bir anket sorusu?")
        token = uuid.uuid4()
        cast(self.poll, 0, token=token)
        cast(other, 0, token=token)
        self.assertEqual(Vote.objects.count(), 2)

    def test_option_must_belong_to_the_poll(self):
        other = make_poll(self.user, question="Başka bir anket sorusu?")
        foreign_option = other.options.get(order=0)
        with self.assertRaises(ValueError):
            Vote.objects.create(poll=self.poll, option=foreign_option, voter_token=uuid.uuid4())
        self.assertEqual(Vote.objects.count(), 0)

    def test_votes_are_removed_with_poll_and_with_user(self):
        voter = make_user("mehmet")
        cast(self.poll, 0, user=voter)
        cast(self.poll, 1, token=uuid.uuid4())
        voter.delete()
        self.assertEqual(Vote.objects.count(), 1)
        self.poll.delete()
        self.assertEqual(Vote.objects.count(), 0)


class VoterTokenMiddlewareTests(TestCase):
    def test_first_visit_sets_a_signed_http_only_cookie(self):
        response = self.client.get(reverse("polls:list"))
        cookie = response.cookies[COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(int(cookie["max-age"]), COOKIE_MAX_AGE)
        self.assertEqual(COOKIE_MAX_AGE, 365 * 24 * 3600)
        self.assertIn(":", cookie.value)  # imzalı: "<değer>:<imza>"
        self.assertTrue(response.wsgi_request.voter_token_is_new)

    def test_cookie_is_secure_outside_debug_only(self):
        self.assertTrue(self.client.get("/").cookies[COOKIE_NAME]["secure"])  # testler DEBUG=False çalışır
        with override_settings(DEBUG=True):
            self.assertFalse(Client().get("/").cookies[COOKIE_NAME]["secure"])

    def test_returning_visitor_keeps_the_same_token_and_gets_no_new_cookie(self):
        first = self.client.get("/")
        second = self.client.get("/")
        self.assertNotIn(COOKIE_NAME, second.cookies)
        self.assertFalse(second.wsgi_request.voter_token_is_new)
        self.assertEqual(first.wsgi_request.voter_token, second.wsgi_request.voter_token)

    def test_tampered_cookie_is_replaced(self):
        first = self.client.get("/")
        self.client.cookies[COOKIE_NAME] = first.cookies[COOKIE_NAME].value + "x"
        second = self.client.get("/")
        self.assertTrue(second.wsgi_request.voter_token_is_new)
        self.assertNotEqual(first.wsgi_request.voter_token, second.wsgi_request.voter_token)
        self.assertIn(COOKIE_NAME, second.cookies)

    def test_validly_signed_but_non_uuid_value_is_replaced(self):
        forged = HttpResponse()
        forged.set_signed_cookie(COOKIE_NAME, "uuid-degil")
        self.client.cookies[COOKIE_NAME] = forged.cookies[COOKIE_NAME].value
        response = self.client.get("/")
        self.assertTrue(response.wsgi_request.voter_token_is_new)
        self.assertIsInstance(response.wsgi_request.voter_token, uuid.UUID)

    def test_different_visitors_get_different_tokens(self):
        a = Client().get("/").wsgi_request.voter_token
        b = Client().get("/").wsgi_request.voter_token
        self.assertNotEqual(a, b)


class VoteViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user("yazar")
        cls.poll = make_poll(cls.author, options=("Sinema", "Müze", "Park"))
        cls.url = reverse("polls:vote", args=[cls.poll.public_id])

    def test_guest_can_vote_once(self):
        visit(self.client, self.poll)
        response = self.client.post(self.url, {"option": "1"})
        self.assertRedirects(response, self.poll.get_absolute_url())  # PRG
        vote = Vote.objects.get()
        self.assertEqual(vote.option.text, "Müze")
        self.assertIsNone(vote.user)
        self.assertIsNotNone(vote.voter_token)
        self.assertIn("Oyun kaydedildi! 🎉", messages_of(response))

    def test_same_guest_cannot_vote_twice(self):
        visit(self.client, self.poll)
        self.client.post(self.url, {"option": "1"})
        response = self.client.post(self.url, {"option": "2"})
        self.assertRedirects(response, self.poll.get_absolute_url())
        self.assertIn("Bu ankete zaten oy verdin.", messages_of(response))
        vote = Vote.objects.get()  # hâlâ tek oy ve değişmedi
        self.assertEqual(vote.option.text, "Müze")

    def test_two_different_guests_can_both_vote(self):
        for order in ("0", "1"):
            guest = Client()
            visit(guest, self.poll)
            guest.post(self.url, {"option": order})
        self.assertEqual(Vote.objects.count(), 2)

    def test_member_votes_once_and_not_twice(self):
        member = make_user("mehmet")
        self.client.force_login(member)
        self.client.post(self.url, {"option": "0"})
        response = self.client.post(self.url, {"option": "2"})
        self.assertIn("Bu ankete zaten oy verdin.", messages_of(response))
        vote = Vote.objects.get()
        self.assertEqual(vote.user, member)
        self.assertIsNone(vote.voter_token)
        self.assertEqual(vote.option.text, "Sinema")

    def test_author_can_vote_on_own_poll(self):
        self.client.force_login(self.author)
        self.client.post(self.url, {"option": "0"})
        self.assertEqual(Vote.objects.get().user, self.author)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(Vote.objects.count(), 0)

    def test_invalid_option_values_are_rejected(self):
        visit(self.client, self.poll)
        for value in ["3", "4", "5", "-1", "abc", "", "1.5", "99999999999"]:
            response = self.client.post(self.url, {"option": value})
            self.assertRedirects(response, self.poll.get_absolute_url())
            self.assertIn("Lütfen bir seçenek seç.", messages_of(response), value)
        response = self.client.post(self.url, {})  # alan hiç gönderilmedi
        self.assertIn("Lütfen bir seçenek seç.", messages_of(response))
        self.assertEqual(Vote.objects.count(), 0)

    def test_option_of_another_poll_cannot_be_reached(self):
        other = make_poll(self.author, question="Beş seçenekli başka anket?", options=("A", "B", "C", "D", "E"))
        visit(self.client, self.poll)
        # Bu anketin yalnızca 0-2 sıraları var; diğer anketin 3-4 sırasına erişilemez.
        self.client.post(self.url, {"option": "4"})
        self.assertEqual(Vote.objects.filter(poll=other).count(), 0)
        self.assertEqual(Vote.objects.count(), 0)

    def test_guest_without_cookie_is_rejected(self):
        response = Client().post(self.url, {"option": "0"})  # sayfa hiç açılmadı → çerez yok
        self.assertRedirects(response, self.poll.get_absolute_url())
        self.assertIn("Oy verebilmek için tarayıcında çerezlere izin vermelisin.", messages_of(response))
        self.assertEqual(Vote.objects.count(), 0)

    def test_member_does_not_need_the_guest_cookie(self):
        member = make_user("mehmet")
        client = Client()
        client.force_login(member)
        client.post(self.url, {"option": "0"})  # çerezsiz (sayfa açılmadan) ama üye
        self.assertEqual(Vote.objects.get().user, member)

    def test_unknown_poll_is_404(self):
        self.assertEqual(self.client.post("/anket/zzzzzzzzzz/oy/", {"option": "0"}).status_code, 404)

    def test_numeric_vote_url_is_404(self):
        self.assertEqual(self.client.post(f"/anket/{self.poll.pk}/oy/", {"option": "0"}).status_code, 404)

    def test_concurrent_duplicate_is_handled_gracefully(self):
        visit(self.client, self.poll)
        with mock.patch("polls.views.Vote.objects.create", side_effect=IntegrityError("yarış")):
            response = self.client.post(self.url, {"option": "0"})
        self.assertRedirects(response, self.poll.get_absolute_url())
        self.assertIn("Bu ankete zaten oy verdin.", messages_of(response))


class ResultVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user("yazar", "gizli.yazar@example.com")
        cls.poll = make_poll(cls.author, options=("Sinema", "Müze", "Park"))
        cls.url = reverse("polls:vote", args=[cls.poll.public_id])

    def test_guest_who_has_not_voted_sees_no_results_but_total(self):
        for order in (0, 0, 1):
            cast(self.poll, order)
        response = visit(self.client, self.poll)
        self.assertContains(response, "Toplam <strong>3</strong> oy")
        self.assertNotContains(response, "result__fill")
        self.assertNotContains(response, "Senin oyun")
        self.assertNotContains(response, "🏆")
        self.assertNotRegex(response.content.decode(), r"%\d+ ·")
        self.assertContains(response, "Oyumu Ver")  # oy formu var

    def test_guest_sees_results_after_voting(self):
        cast(self.poll, 0)
        visit(self.client, self.poll)
        self.client.post(self.url, {"option": "1"})
        response = self.client.get(self.poll.get_absolute_url())
        self.assertContains(response, "result__fill")
        self.assertContains(response, "✓ Senin oyun")
        self.assertContains(response, "%50 · 1 oy")
        self.assertNotContains(response, "Oyumu Ver")
        self.assertContains(response, "Oyunu verdin, teşekkürler")

    def test_my_vote_badge_marks_only_my_option(self):
        visit(self.client, self.poll)
        self.client.post(self.url, {"option": "2"})
        html = self.client.get(self.poll.get_absolute_url()).content.decode()
        self.assertEqual(html.count("✓ Senin oyun"), 1)
        self.assertLess(html.index("Park"), html.index("✓ Senin oyun"))

    def test_member_sees_results_after_voting_but_not_before(self):
        member = make_user("mehmet")
        self.client.force_login(member)
        self.assertNotContains(self.client.get(self.poll.get_absolute_url()), "result__fill")
        self.client.post(self.url, {"option": "0"})
        self.assertContains(self.client.get(self.poll.get_absolute_url()), "result__fill")

    def test_author_always_sees_results_and_can_still_vote(self):
        cast(self.poll, 1)
        self.client.force_login(self.author)
        response = self.client.get(self.poll.get_absolute_url())
        self.assertContains(response, "result__fill")
        self.assertContains(response, "Sen de oy verebilirsin")
        self.assertContains(response, "Oyumu Ver")
        self.assertNotContains(response, "Senin oyun")  # sahibi henüz oy vermedi

    def test_percentages_and_counts(self):
        for order in (0, 0, 1):
            cast(self.poll, order)
        self.client.force_login(self.author)
        html = self.client.get(self.poll.get_absolute_url()).content.decode()
        self.assertIn("%67 · 2 oy", html)
        self.assertIn("%33 · 1 oy", html)
        self.assertIn("%0 · 0 oy", html)
        self.assertIn("width: 67%", html)

    def test_percent_rounds_half_up(self):
        self.assertEqual(_percent(1, 8), 13)  # 12,5 → 13 (banker yuvarlaması 12 verirdi)
        self.assertEqual(_percent(7, 8), 88)
        self.assertEqual(_percent(1, 3), 33)
        self.assertEqual(_percent(2, 3), 67)
        self.assertEqual(_percent(0, 0), 0)
        self.assertEqual(_percent(5, 5), 100)

    def test_trophy_goes_to_the_top_option_and_to_all_ties(self):
        cast(self.poll, 0)
        cast(self.poll, 0)
        cast(self.poll, 1)
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(self.poll.get_absolute_url()).content.decode().count("🏆"), 1)
        cast(self.poll, 1)  # 2-2 beraberlik
        self.assertEqual(self.client.get(self.poll.get_absolute_url()).content.decode().count("🏆"), 2)

    def test_no_trophy_when_there_are_no_votes(self):
        self.client.force_login(self.author)
        response = self.client.get(self.poll.get_absolute_url())
        self.assertNotContains(response, "🏆")
        self.assertContains(response, "%0 · 0 oy")
        self.assertContains(response, "Toplam <strong>0</strong> oy")

    def test_privacy_no_emails_and_no_numeric_ids(self):
        poll = Poll.objects.create(id=9137, author=self.author, question="Sızıntı var mı bu sayfada?")
        for i, text in enumerate(["Bir", "İki"]):
            Option.objects.create(id=60120 + i, poll=poll, text=text, order=i)
        voter = make_user("mehmet", "gizli.mehmet@example.com")
        Vote.objects.create(id=77451, poll=poll, option=poll.options.get(order=0), user=voter)
        for who in (self.author, voter):
            self.client.force_login(who)
            html = self.client.get(poll.get_absolute_url()).content.decode()
            for needle in ["9137", "60120", "60121", "77451", "gizli.yazar@example.com", "gizli.mehmet@example.com"]:
                self.assertNotIn(needle, html)
            self.assertNotIn("data-id", html)


class ListVoteCountTests(TestCase):
    def test_card_shows_distinct_vote_count(self):
        author = make_user()
        poll = make_poll(author, options=("A", "B", "C"))
        for order in (0, 0, 1, 2):
            cast(poll, order)
        response = self.client.get(reverse("polls:list"))
        self.assertContains(response, "3 seçenek")
        self.assertContains(response, "4 oy")  # join çarpımı olsaydı 12 görünürdü

    def test_query_count_stays_constant_with_votes(self):
        author = make_user()
        first = make_poll(author, question="Birinci anket sorusu?")
        cast(first, 0)
        with CaptureQueriesContext(connection) as few:
            self.client.get(reverse("polls:list"))
        for i in range(8):
            poll = make_poll(author, question=f"Oylu anket sorusu {i:02d}?")
            cast(poll, 0)
            cast(poll, 1)
        with CaptureQueriesContext(connection) as many:
            self.client.get(reverse("polls:list"))
        self.assertEqual(len(few), len(many))


class VoteAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("yonetici", "yonetici@example.com", PASSWORD)
        cls.poll = make_poll(cls.admin)
        cls.vote = cast(cls.poll, 0, user=cls.admin)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_vote_pages_open_but_adding_is_forbidden(self):
        self.assertEqual(self.client.get(reverse("admin:polls_vote_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:polls_vote_change", args=[self.vote.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:polls_vote_add")).status_code, 403)

    def test_vote_can_be_deleted_for_moderation(self):
        response = self.client.post(reverse("admin:polls_vote_delete", args=[self.vote.pk]), {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Vote.objects.count(), 0)
