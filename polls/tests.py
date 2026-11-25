import re
from unittest import mock

from django.db import IntegrityError, connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .models import PUBLIC_ID_ALPHABET, PUBLIC_ID_LENGTH, Option, Poll, generate_public_id

PASSWORD = "gucluSifre123"
PUBLIC_ID_RE = re.compile(r"^[%s]{%d}$" % (PUBLIC_ID_ALPHABET, PUBLIC_ID_LENGTH))


def make_user(username="ahmet", email=None):
    return User.objects.create_user(username, email or f"{username}@example.com", PASSWORD)


def make_poll(author, question="Bugün sinemaya mı gitsem, müzeye mi?", options=("Sinema", "Müze"), **extra):
    poll = Poll.objects.create(author=author, question=question, **extra)
    Option.objects.bulk_create([Option(poll=poll, text=text, order=i) for i, text in enumerate(options)])
    return poll


class HomePageTests(TestCase):
    def test_home_page_renders(self):
        response = self.client.get(reverse("polls:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kararsızım")
        self.assertContains(response, 'lang="tr"')

    def test_empty_state(self):
        response = self.client.get(reverse("polls:list"))
        self.assertContains(response, "Henüz kimse kararsız değil")
        self.assertContains(response, "İlk anketi sen aç!")


class PublicIdTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()

    def test_generated_code_has_expected_shape(self):
        for _ in range(200):
            self.assertRegex(generate_public_id(), PUBLIC_ID_RE)

    def test_new_poll_gets_a_code_and_url(self):
        poll = make_poll(self.user)
        self.assertRegex(poll.public_id, PUBLIC_ID_RE)
        self.assertEqual(poll.get_absolute_url(), f"/anket/{poll.public_id}/")

    def test_consecutive_codes_are_unique_and_not_sequential(self):
        codes = [make_poll(self.user, question=f"Sıralı mı bu kod {i:02d}?").public_id for i in range(20)]
        self.assertEqual(len(set(codes)), 20)
        # Sıralı artan (ya da azalan) bir sayaç gibi davranmıyor.
        self.assertNotEqual(codes, sorted(codes))
        self.assertNotEqual(codes, sorted(codes, reverse=True))

    def test_code_never_changes_on_later_saves(self):
        poll = make_poll(self.user)
        original = poll.public_id
        poll.question = "Başka bir soru olsun mu?"
        poll.save()
        poll.refresh_from_db()
        self.assertEqual(poll.public_id, original)

    def test_collision_is_retried_with_a_new_code(self):
        existing = make_poll(self.user)
        with mock.patch("polls.models.generate_public_id", side_effect=[existing.public_id, "k7m2qx9fha"]) as gen:
            poll = Poll.objects.create(author=self.user, question="Çakışma sonrası yeni kod alır mı?")
        self.assertEqual(gen.call_count, 2)
        self.assertEqual(poll.public_id, "k7m2qx9fha")
        self.assertEqual(Poll.objects.count(), 2)

    def test_gives_up_after_five_collisions(self):
        existing = make_poll(self.user)
        with mock.patch("polls.models.generate_public_id", return_value=existing.public_id) as gen:
            with self.assertRaises(IntegrityError):
                Poll.objects.create(author=self.user, question="Hep aynı kod geliyor")
        self.assertEqual(gen.call_count, 5)
        self.assertEqual(Poll.objects.count(), 1)

    def test_numeric_address_is_404(self):
        poll = make_poll(self.user)
        self.assertEqual(self.client.get(f"/anket/{poll.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/anket/1/").status_code, 404)

    def test_malformed_codes_are_404(self):
        poll = make_poll(self.user)
        bad_codes = [
            poll.public_id.upper(),            # büyük harf
            poll.public_id[:-1],               # çok kısa
            poll.public_id + "a",              # çok uzun
            "0123456789",                      # alfabede olmayan karakterler
            "ooooooooii",
            "abcdefghi!",
        ]
        for code in bad_codes:
            self.assertEqual(self.client.get(f"/anket/{code}/").status_code, 404, code)

    def test_unknown_but_well_formed_code_is_404(self):
        self.assertEqual(self.client.get("/anket/zzzzzzzzzz/").status_code, 404)

    def test_create_path_is_not_shadowed_by_converter(self):
        self.assertEqual(reverse("polls:create"), "/anket/yeni/")
        self.assertEqual(self.client.get("/anket/yeni/").status_code, 302)  # misafir → giriş


class OptionModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.poll = make_poll(make_user())

    def test_order_is_unique_per_poll(self):
        with self.assertRaises(IntegrityError):
            Option.objects.create(poll=self.poll, text="Yinelenen sıra", order=0)

    def test_order_must_be_in_range(self):
        with self.assertRaises(IntegrityError):
            Option.objects.create(poll=self.poll, text="Aralık dışı", order=5)

    def test_options_come_back_in_order(self):
        poll = make_poll(make_user("mehmet"), options=("A", "B", "C"))
        self.assertEqual([o.text for o in poll.options.all()], ["A", "B", "C"])


class PollCreateTests(TestCase):
    url = reverse("polls:create")

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()

    def setUp(self):
        self.client.force_login(self.user)

    def post(self, question="Bugün sinemaya mı gitsem, müzeye mi?", options=("Sinema", "Müze"), **extra):
        data = {"question": question, "option": list(options)}
        data.update(extra)
        return self.client.post(self.url, data)

    def test_guest_is_redirected_to_login_with_message(self):
        self.client.logout()
        response = self.client.get(self.url, follow=True)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next=/anket/yeni/")
        self.assertContains(response, "Anket oluşturmak için giriş yapmalısın.")

    def test_guest_cannot_post(self):
        self.client.logout()
        response = self.post()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Poll.objects.count(), 0)

    def test_form_shows_five_inputs_and_first_two_are_required(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(len(re.findall(r'name="option"', html)), 5)
        self.assertEqual(len(re.findall(r'name="option"[^>]*required', html)), 2)

    def test_two_options_succeed(self):
        response = self.post(options=("Sinema", "Müze"))
        poll = Poll.objects.get()
        self.assertRedirects(response, poll.get_absolute_url())
        self.assertEqual(poll.author, self.user)
        self.assertEqual([o.text for o in poll.options.all()], ["Sinema", "Müze"])

    def test_five_options_succeed(self):
        self.post(options=("A", "B", "C", "D", "E"))
        poll = Poll.objects.get()
        self.assertEqual([(o.order, o.text) for o in poll.options.all()], [(0, "A"), (1, "B"), (2, "C"), (3, "D"), (4, "E")])

    def test_blank_options_are_ignored_and_order_is_compact(self):
        self.post(options=("Sinema", "", "Müze", "   ", ""))
        poll = Poll.objects.get()
        self.assertEqual([(o.order, o.text) for o in poll.options.all()], [(0, "Sinema"), (1, "Müze")])

    def test_success_shows_message_on_detail_page(self):
        response = self.client.post(self.url, {"question": "Hangi telefonu alsam?", "option": ["Bir", "İki"]}, follow=True)
        self.assertContains(response, "Anketin yayında!")

    def test_one_option_is_rejected(self):
        response = self.post(options=("Sadece biri", "", "", "", ""))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "En az 2 seçenek girmelisin.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_six_options_are_rejected(self):
        response = self.post(options=("A", "B", "C", "D", "E", "F"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "En fazla 5 seçenek ekleyebilirsin.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_duplicate_options_are_rejected_case_insensitively(self):
        response = self.post(options=("Sinema", "SINEMA"))
        self.assertContains(response, "Aynı seçeneği birden fazla kez yazmışsın.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_option_longer_than_100_chars_is_rejected(self):
        response = self.post(options=("a" * 101, "b"))
        self.assertContains(response, "Her seçenek en fazla 100 karakter olabilir.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_question_length_limits(self):
        self.assertEqual(Poll.objects.count(), 0)
        for question in ["kısa", "", "   ", "x" * 201]:
            response = self.post(question=question)
            self.assertEqual(response.status_code, 200, question)
        self.assertEqual(Poll.objects.count(), 0)
        self.post(question="x" * 200)
        self.assertEqual(Poll.objects.count(), 1)

    def test_question_is_stripped(self):
        self.post(question="   Çay mı kahve mi?   ")
        self.assertEqual(Poll.objects.get().question, "Çay mı kahve mi?")

    def test_errors_keep_what_the_user_typed(self):
        response = self.post(question="Çay mı kahve mi?", options=("Çay", "çay", "", "", ""))
        self.assertContains(response, 'value="Çay"')
        self.assertContains(response, "Çay mı kahve mi?")

    def test_poll_and_options_are_saved_atomically(self):
        with mock.patch("polls.forms.Option.objects.bulk_create", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.post()
        self.assertEqual(Poll.objects.count(), 0)


class PollListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("ahmet", "gizli.ahmet@example.com")

    def test_lists_newest_first_with_author_username_only(self):
        old = make_poll(self.user, question="Eski anket sorusu?")
        new = make_poll(self.user, question="Yeni anket sorusu?")
        Poll.objects.filter(pk=old.pk).update(created_at=timezone.now() - timezone.timedelta(days=2))
        response = self.client.get(reverse("polls:list"))
        html = response.content.decode()
        self.assertLess(html.index("Yeni anket sorusu?"), html.index("Eski anket sorusu?"))
        self.assertContains(response, "@ahmet")
        self.assertNotContains(response, "gizli.ahmet@example.com")
        self.assertContains(response, new.get_absolute_url())

    def test_card_shows_option_count(self):
        make_poll(self.user, options=("A", "B", "C"))
        self.assertContains(self.client.get(reverse("polls:list")), "3 seçenek")

    def test_pagination_ten_per_page(self):
        for i in range(25):
            make_poll(self.user, question=f"Soru numarası {i:02d} nedir?")
        first = self.client.get(reverse("polls:list"))
        self.assertEqual(len(first.context["page"].object_list), 10)
        self.assertContains(first, "Sayfa 1 / 3")
        last = self.client.get(reverse("polls:list"), {"page": 3})
        self.assertEqual(len(last.context["page"].object_list), 5)

    def test_invalid_page_does_not_crash(self):
        make_poll(self.user)
        for page in ["abc", "999", "-1", ""]:
            self.assertEqual(self.client.get(reverse("polls:list"), {"page": page}).status_code, 200, page)

    def test_query_count_does_not_grow_with_polls(self):
        make_poll(self.user, question="Tek anket varken sorgu sayısı?")
        with CaptureQueriesContext(connection) as few:
            self.client.get(reverse("polls:list"))
        for i in range(9):
            make_poll(self.user, question=f"Sorgu sayısı sorusu {i:02d}?")
        with CaptureQueriesContext(connection) as many:
            self.client.get(reverse("polls:list"))
        self.assertEqual(len(few), len(many))  # N+1 yok: yazar ve seçenek sayısı tek sorguda gelir


class PollDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("ahmet", "gizli.ahmet@example.com")
        cls.poll = make_poll(cls.user, options=("Sinema", "Müze", "Park"))

    def test_shows_question_author_and_options_in_order(self):
        response = self.client.get(self.poll.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.poll.question)
        self.assertContains(response, "@ahmet")
        html = response.content.decode()
        self.assertLess(html.index("Sinema"), html.index("Müze"))
        self.assertLess(html.index("Müze"), html.index("Park"))

    def test_radio_values_are_orders_not_ids(self):
        poll = Poll.objects.create(author=self.user, question="Radio değerleri sıra mı id mi?")
        for order, text in enumerate(["Bir", "İki", "Üç"]):
            Option.objects.create(id=48000 + order, poll=poll, text=text, order=order)
        response = self.client.get(poll.get_absolute_url())
        values = re.findall(r'type="radio"[^>]*value="(\d+)"', response.content.decode())
        self.assertEqual(values, ["0", "1", "2"])

    def test_vote_form_posts_to_vote_url(self):
        response = self.client.get(self.poll.get_absolute_url())
        self.assertContains(response, f'action="/anket/{self.poll.public_id}/oy/"')
        self.assertNotContains(response, "<fieldset disabled>")

    def test_title_and_description(self):
        response = self.client.get(self.poll.get_absolute_url())
        self.assertContains(response, f"<title>{self.poll.question} · Kararsızım</title>")

    def test_author_email_is_not_leaked(self):
        self.assertNotContains(self.client.get(self.poll.get_absolute_url()), "gizli.ahmet@example.com")


class NumericIdLeakTests(TestCase):
    """Anket ve seçeneklerin sayısal id'si hiçbir sayfada görünmemeli (plan 5.2.1)."""

    def test_numeric_ids_do_not_appear_in_html(self):
        author = make_user()
        poll = Poll.objects.create(id=7351, author=author, question="Sayısal id sızıyor mu acaba?")
        for i, text in enumerate(["Evet", "Hayır", "Belki"]):
            Option.objects.create(id=48210 + i, poll=poll, text=text, order=i)

        self.client.force_login(author)
        pages = [
            self.client.get(reverse("polls:list")),
            self.client.get(poll.get_absolute_url()),
            self.client.get(reverse("polls:create")),
        ]
        secrets_to_hide = ["7351", "48210", "48211", "48212"]
        for response in pages:
            html = response.content.decode()
            for needle in secrets_to_hide:
                self.assertNotIn(needle, html)
            self.assertNotIn("data-id", html)
            self.assertNotIn("data-poll", html)

    def test_no_numeric_poll_urls_are_generated(self):
        author = make_user()
        poll = make_poll(author)
        html = self.client.get(reverse("polls:list")).content.decode()
        self.assertNotRegex(html, r'/anket/\d+/')
        self.assertIn(f"/anket/{poll.public_id}/", html)


class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("yonetici", "yonetici@example.com", PASSWORD)
        cls.poll = make_poll(cls.admin)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_admin_pages_open(self):
        for name, args in [
            ("admin:polls_poll_changelist", []),
            ("admin:polls_poll_add", []),
            ("admin:polls_poll_change", [self.poll.pk]),
        ]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)

    def test_public_id_is_listed_searchable_and_readonly(self):
        listing = self.client.get(reverse("admin:polls_poll_changelist"))
        self.assertContains(listing, self.poll.public_id)
        found = self.client.get(reverse("admin:polls_poll_changelist"), {"q": self.poll.public_id})
        self.assertContains(found, self.poll.question)
        change = self.client.get(reverse("admin:polls_poll_change", args=[self.poll.pk]))
        self.assertNotContains(change, 'name="public_id"')  # düzenlenebilir alan değil, salt okunur

    def test_poll_created_in_admin_gets_a_code(self):
        response = self.client.post(
            reverse("admin:polls_poll_add"),
            {
                "author": self.admin.pk,
                "question": "Admin'den açılan anket nasıl?",
                "options-TOTAL_FORMS": "2",
                "options-INITIAL_FORMS": "0",
                "options-MIN_NUM_FORMS": "0",
                "options-MAX_NUM_FORMS": "5",
                "options-0-text": "İyi",
                "options-0-order": "0",
                "options-1-text": "Kötü",
                "options-1-order": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Poll.objects.get(question="Admin'den açılan anket nasıl?")
        self.assertRegex(created.public_id, PUBLIC_ID_RE)


class SinceFilterTests(TestCase):
    def test_recent_is_just_now(self):
        from polls.templatetags.poll_extras import since

        self.assertEqual(since(timezone.now()), "az önce")

    def test_older_uses_timesince(self):
        from polls.templatetags.poll_extras import since

        # timesince birimler arasında bölünmeyen boşluk (NBSP) kullanır.
        self.assertEqual(since(timezone.now() - timezone.timedelta(hours=2, minutes=5)), "2\xa0saat önce")

    def test_cards_show_just_now_for_new_polls(self):
        make_poll(make_user())
        self.assertContains(self.client.get(reverse("polls:list")), "az önce")
