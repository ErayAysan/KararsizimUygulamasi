"""Faz 6: süreli anketler (bitiş zamanı, oy kapanması, aktif/süresi dolan sekmeleri, renkli sonuçlar)."""

from datetime import timedelta

from django.http import QueryDict
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import PollForm
from .models import Poll, Vote
from .test_voting import cast, messages_of, visit
from .tests import make_poll, make_user
from .views import _rank_step


def closed_poll(author, **kwargs):
    return make_poll(author, ends_at=timezone.now() - timedelta(hours=1), **kwargs)


class PollDeadlineModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()

    def test_poll_without_deadline_never_closes(self):
        poll = make_poll(self.user)
        self.assertIsNone(poll.ends_at)
        self.assertFalse(poll.is_closed)

    def test_future_deadline_is_open_and_past_deadline_is_closed(self):
        open_poll = make_poll(self.user, ends_at=timezone.now() + timedelta(hours=2))
        ended = closed_poll(self.user)
        self.assertFalse(open_poll.is_closed)
        self.assertTrue(ended.is_closed)

    def test_active_and_closed_querysets_partition_polls(self):
        forever = make_poll(self.user, question="Süresiz anket")
        running = make_poll(self.user, question="Süren anket", ends_at=timezone.now() + timedelta(days=1))
        ended = closed_poll(self.user, question="Biten anket")
        self.assertCountEqual(Poll.objects.active(), [forever, running])
        self.assertCountEqual(Poll.objects.closed(), [ended])


class PollFormDurationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()

    def submit(self, duration=None):
        data = QueryDict(mutable=True)
        data["question"] = "Bugün sinemaya mı gitsem?"
        data.setlist("option", ["Sinema", "Müze"])
        if duration is not None:
            data["duration"] = duration
        form = PollForm(data)
        return form, form.is_valid()

    def test_default_is_no_deadline(self):
        form, valid = self.submit()
        self.assertTrue(valid)
        self.assertIsNone(form.save(author=self.user).ends_at)

    def test_zero_means_no_deadline(self):
        form, valid = self.submit("0")
        self.assertTrue(valid)
        self.assertIsNone(form.save(author=self.user).ends_at)

    def test_preset_sets_deadline_from_now(self):
        form, valid = self.submit("24")
        self.assertTrue(valid)
        before = timezone.now()
        poll = form.save(author=self.user)
        delta = poll.ends_at - before
        self.assertAlmostEqual(delta.total_seconds(), 24 * 3600, delta=60)

    def test_unknown_duration_is_rejected(self):
        form, valid = self.submit("9999")
        self.assertFalse(valid)
        self.assertIn("duration", form.errors)

    def test_create_page_offers_duration_select_with_presets(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("polls:create"))
        self.assertContains(response, 'name="duration"')
        for label in ("Süresiz", "1 saat", "6 saat", "1 gün", "3 gün", "1 hafta"):
            self.assertContains(response, label)

    def test_create_view_stores_deadline(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("polls:create"),
            {"question": "Hangi filme gitsem?", "option": ["A filmi", "B filmi"], "duration": "6"},
        )
        self.assertEqual(response.status_code, 302)
        poll = Poll.objects.get(question="Hangi filme gitsem?")
        self.assertIsNotNone(poll.ends_at)
        self.assertGreater(poll.ends_at, timezone.now() + timedelta(hours=5))


class ClosedPollVotingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.poll = closed_poll(cls.author)

    def test_guest_cannot_vote_after_deadline(self):
        client = Client()
        visit(client, self.poll)
        response = client.post(reverse("polls:vote", args=[self.poll.public_id]), {"option": "0"})
        self.assertRedirects(response, self.poll.get_absolute_url())
        self.assertEqual(Vote.objects.count(), 0)
        self.assertIn("Bu anketin süresi doldu, artık oy verilemiyor.", messages_of(response))

    def test_member_cannot_vote_after_deadline(self):
        voter = make_user("ayse")
        self.client.force_login(voter)
        self.client.post(reverse("polls:vote", args=[self.poll.public_id]), {"option": "1"})
        self.assertEqual(Vote.objects.count(), 0)

    def test_voting_still_works_before_deadline(self):
        poll = make_poll(self.author, ends_at=timezone.now() + timedelta(hours=1))
        voter = make_user("ayse")
        self.client.force_login(voter)
        self.client.post(reverse("polls:vote", args=[poll.public_id]), {"option": "0"})
        self.assertEqual(Vote.objects.filter(poll=poll).count(), 1)


class ClosedPollDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.poll = closed_poll(cls.author, options=("Evet", "Hayır", "Kararsızım"))
        for _ in range(5):
            cast(cls.poll, 0)
        for _ in range(4):
            cast(cls.poll, 1)
        cast(cls.poll, 2)

    def test_everyone_sees_results_and_no_vote_form(self):
        response = Client().get(self.poll.get_absolute_url())
        self.assertContains(response, "%50 · 5 oy")
        self.assertContains(response, "%40 · 4 oy")
        self.assertContains(response, "%10 · 1 oy")
        self.assertContains(response, "Süresi doldu")
        self.assertNotContains(response, 'name="option"')
        self.assertNotContains(response, "Oyumu Ver")
        self.assertNotContains(response, "teşekkürler")

    def test_bars_run_from_green_to_red(self):
        response = Client().get(self.poll.get_absolute_url())
        html = response.content.decode()
        self.assertIn("rank-4", html)  # en çok oy: yeşil
        self.assertIn("rank-0", html)  # en az oy: kırmızı
        self.assertLess(html.index("rank-4"), html.index("rank-0"))

    def test_poll_with_no_votes_has_no_rank_colors(self):
        empty = closed_poll(self.author, question="Kimse oy vermedi mi?")
        response = Client().get(empty.get_absolute_url())
        self.assertNotContains(response, "rank-")
        self.assertContains(response, "%0 · 0 oy")

    def test_open_poll_with_deadline_hides_results_from_non_voters(self):
        poll = make_poll(self.author, ends_at=timezone.now() + timedelta(days=2))
        cast(poll, 0)
        response = Client().get(poll.get_absolute_url())
        self.assertNotContains(response, "result__numbers")  # yüzde/oy satırı yok
        self.assertContains(response, "kaldı")
        self.assertContains(response, 'name="option"')

    def test_ended_poll_has_no_numeric_id_leak(self):
        html = Client().get(self.poll.get_absolute_url()).content.decode()
        self.assertNotIn(f'value="{self.poll.id}"', html)


class RankStepTests(TestCase):
    def test_highest_is_green_and_lowest_is_red(self):
        self.assertEqual(_rank_step(5, 1, 5), 4)
        self.assertEqual(_rank_step(1, 1, 5), 0)

    def test_values_in_between_are_proportional(self):
        self.assertEqual(_rank_step(3, 1, 5), 2)

    def test_all_equal_counts_are_all_green(self):
        self.assertEqual(_rank_step(2, 2, 2), 4)


class PollListTabsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.forever = make_poll(cls.author, question="Süresiz soru burada")
        cls.running = make_poll(cls.author, question="Süren soru burada", ends_at=timezone.now() + timedelta(days=1))
        cls.ended = closed_poll(cls.author, question="Biten soru burada")

    def test_active_tab_lists_running_and_unlimited_polls_only(self):
        response = self.client.get(reverse("polls:list"))
        self.assertContains(response, "Süresiz soru burada")
        self.assertContains(response, "Süren soru burada")
        self.assertNotContains(response, "Biten soru burada")

    def test_ended_tab_lists_closed_polls_only(self):
        response = self.client.get(reverse("polls:list"), {"durum": "bitti"})
        self.assertContains(response, "Biten soru burada")
        self.assertNotContains(response, "Süresiz soru burada")
        self.assertNotContains(response, "Süren soru burada")
        self.assertContains(response, "Sonuçlara bak")

    def test_unknown_status_falls_back_to_active_tab(self):
        response = self.client.get(reverse("polls:list"), {"durum": "xyz"})
        self.assertContains(response, "Süresiz soru burada")

    def test_tabs_mark_the_current_one_for_screen_readers(self):
        active = self.client.get(reverse("polls:list")).content.decode()
        ended = self.client.get(reverse("polls:list"), {"durum": "bitti"}).content.decode()
        self.assertEqual(active.count('aria-current="page"'), 1)
        self.assertEqual(ended.count('aria-current="page"'), 1)
        self.assertIn("Aktif anketler", active)
        self.assertIn("Süresi dolanlar", ended)

    def test_empty_ended_tab_has_friendly_message(self):
        Poll.objects.closed().delete()
        response = self.client.get(reverse("polls:list"), {"durum": "bitti"})
        self.assertContains(response, "Süresi dolan anket yok")

    def test_ended_tab_pagination_keeps_status(self):
        for i in range(11):
            closed_poll(self.author, question=f"Eski anket numara {i}")
        response = self.client.get(reverse("polls:list"), {"durum": "bitti"})
        self.assertContains(response, "durum=bitti&amp;page=2")

    def test_list_does_not_show_author_email(self):
        response = self.client.get(reverse("polls:list"), {"durum": "bitti"})
        self.assertNotContains(response, self.author.email)
