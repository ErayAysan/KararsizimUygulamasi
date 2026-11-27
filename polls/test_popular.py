"""Faz 7: Popüler sekmesi (aktif anketler, çok oydan aza)."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .test_voting import cast
from .tests import make_poll, make_user


def popular(client, **params):
    return client.get(reverse("polls:list"), {"durum": "populer", **params})


class PopularTabTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.few = make_poll(cls.author, question="Az oy alan anket sorusu")
        cls.many = make_poll(cls.author, question="Çok oy alan anket sorusu")
        cls.none = make_poll(cls.author, question="Hiç oy almayan anket sorusu")
        for _ in range(2):
            cast(cls.few, 0)
        for _ in range(5):
            cast(cls.many, 0)

    def test_polls_are_ordered_by_votes_most_first(self):
        html = popular(self.client).content.decode()
        self.assertLess(html.index("Çok oy alan anket sorusu"), html.index("Az oy alan anket sorusu"))

    def test_polls_without_votes_are_not_popular(self):
        self.assertNotContains(popular(self.client), "Hiç oy almayan anket sorusu")

    def test_vote_counts_are_not_inflated_by_options(self):
        # İki ilişki aynı sorguda sayılır; distinct olmazsa 5 oy x 2 seçenek = 10 görünürdü.
        self.assertContains(popular(self.client), "5 oy")
        self.assertNotContains(popular(self.client), "10 oy")

    def test_equal_votes_show_the_newer_poll_first(self):
        older = make_poll(self.author, question="Eşit oylu eski anket")
        newer = make_poll(self.author, question="Eşit oylu yeni anket")
        for poll in (older, newer):
            for _ in range(7):
                cast(poll, 0)
        html = popular(self.client).content.decode()
        self.assertLess(html.index("Eşit oylu yeni anket"), html.index("Eşit oylu eski anket"))

    def test_closed_polls_are_not_listed_as_popular(self):
        ended = make_poll(self.author, question="Süresi dolmuş popüler anket", ends_at=timezone.now() - timedelta(hours=1))
        for _ in range(50):
            cast(ended, 0)
        self.assertNotContains(popular(self.client), "Süresi dolmuş popüler anket")

    def test_running_polls_with_a_deadline_can_be_popular(self):
        running = make_poll(self.author, question="Süreli ama sürüyor anketi", ends_at=timezone.now() + timedelta(days=1))
        for _ in range(9):
            cast(running, 0)
        html = popular(self.client).content.decode()
        self.assertIn("Süreli ama sürüyor anketi", html)
        self.assertLess(html.index("Süreli ama sürüyor anketi"), html.index("Çok oy alan anket sorusu"))

    def test_popular_polls_do_not_appear_in_the_ended_tab(self):
        response = self.client.get(reverse("polls:list"), {"durum": "bitti"})
        self.assertNotContains(response, "Çok oy alan anket sorusu")

    def test_deleted_poll_disappears_from_popular(self):
        self.many.delete()
        self.assertNotContains(popular(self.client), "Çok oy alan anket sorusu")


class PopularTabPageTests(TestCase):
    def test_tab_is_marked_current_for_screen_readers(self):
        make_poll(make_user(), question="Popüler olacak soru")
        html = popular(self.client).content.decode()
        self.assertEqual(html.count('aria-current="page"'), 1)
        self.assertIn('aria-current="page"><span aria-hidden="true">🔥</span> Popüler</a>', html)
        self.assertIn("<title>Popüler anketler · Kararsızım</title>", html)

    def test_three_tabs_exist_on_every_list_view(self):
        for params in ({}, {"durum": "populer"}, {"durum": "bitti"}):
            html = self.client.get(reverse("polls:list"), params).content.decode()
            for label in ("Aktif anketler", "Popüler", "Süresi dolanlar"):
                self.assertIn(label, html)

    def test_empty_popular_tab_has_a_friendly_message(self):
        make_poll(make_user(), question="Oy almamış soru")
        response = popular(self.client)
        self.assertContains(response, "Henüz popüler anket yok")
        self.assertNotContains(response, "Oy almamış soru")

    def test_unknown_status_falls_back_to_active(self):
        make_poll(make_user(), question="Aktif sekmede görünmeli")
        self.assertContains(self.client.get(reverse("polls:list"), {"durum": "xyz"}), "Aktif sekmede görünmeli")

    def test_pagination_keeps_the_popular_tab(self):
        author = make_user()
        for i in range(11):
            poll = make_poll(author, question=f"Popüler sayfalama {i}")
            cast(poll, 0)
        html = popular(self.client).content.decode()
        self.assertIn("durum=populer&amp;page=2", html)
        self.assertIn("Sonraki →", html)
        page2 = popular(self.client, page=2).content.decode()
        self.assertIn("durum=populer&amp;page=1", page2)
        self.assertIn("← Önceki", page2)

    def test_active_tab_pagination_has_no_status_parameter(self):
        author = make_user()
        for i in range(11):
            make_poll(author, question=f"Aktif sayfalama {i}")
        html = self.client.get(reverse("polls:list")).content.decode()
        self.assertIn('href="?page=2"', html)

    def test_popular_page_never_leaks_email_or_numeric_ids(self):
        author = make_user()
        poll = make_poll(author, question="Sızıntı denemesi sorusu")
        cast(poll, 0)
        html = popular(self.client).content.decode()
        self.assertNotIn(author.email, html)
        self.assertNotIn(f"/anket/{poll.pk}/", html)
