"""Faz 7: ekran okuyucu, renk körlüğü ve mobil erişilebilirlik testleri."""

import re
from datetime import timedelta

from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .test_design import CSS_PATH, JS_PATH
from .test_voting import cast
from .tests import make_poll, make_user

REGISTER_ERRORS = {"username": "a", "email": "x", "password1": "1", "password2": "2"}


class FormErrorAssociationTests(TestCase):
    """`aria-describedby`, var olan bir kimliği göstermeli (aksi hâlde ekran okuyucu hatayı okumaz)."""

    def test_every_describedby_target_exists_on_the_register_page(self):
        html = self.client.post(reverse("accounts:register"), REGISTER_ERRORS).content.decode()
        ids = set(re.findall(r'id="([^"]+)"', html))
        targets = [t for value in re.findall(r'aria-describedby="([^"]+)"', html) for t in value.split()]
        self.assertTrue(targets)
        for target in targets:
            self.assertIn(target, ids, f"aria-describedby hedefi yok: {target}")

    def test_errors_are_announced_with_role_alert(self):
        response = self.client.post(reverse("accounts:register"), REGISTER_ERRORS)
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, 'aria-invalid="true"')


class MessageTests(TestCase):
    def test_success_message_has_an_icon_and_a_hidden_text_label(self):
        self.client.force_login(make_user())
        response = self.client.post(
            reverse("polls:create"), {"question": "Hangi filme gitsem?", "option": ["A", "B"]}, follow=True
        )
        html = response.content.decode()
        self.assertIn("message__icon", html)
        self.assertIn("Başarılı:", html)
        self.assertIn('role="status"', html)

    def test_error_messages_use_role_alert_and_a_text_label(self):
        poll = make_poll(make_user())
        client = Client()
        client.get(poll.get_absolute_url())
        response = client.post(reverse("polls:vote", args=[poll.public_id]), {"option": "9"}, follow=True)
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, "Hata:")


class ScreenReaderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.poll = make_poll(cls.author, question="Sinemaya mı gitsem, müzeye mi?")

    def test_decorative_emojis_are_hidden_from_screen_readers(self):
        urls = (
            reverse("polls:list"),
            reverse("accounts:login"),
            reverse("accounts:register"),
            self.poll.get_absolute_url(),
        )
        for url in urls:
            body = self.client.get(url).content.decode().split("<body>", 1)[1]
            body = re.sub(r'<span aria-hidden="true">[^<]*</span>', "", body)
            body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", body, flags=re.S)
            text = re.sub(r"<[^>]+>", " ", body)
            self.assertNotRegex(text, "[\U0001F300-\U0001FAFF☀-➿⬀-⯿]", url)

    def test_poll_card_link_names_the_poll(self):
        html = self.client.get(reverse("polls:list")).content.decode()
        self.assertIn('Oy ver<span class="visually-hidden">: Sinemaya mı gitsem, müzeye mi?</span>', html)

    def test_vote_group_is_named_after_the_question(self):
        html = self.client.get(self.poll.get_absolute_url()).content.decode()
        self.assertIn("Sinemaya mı gitsem, müzeye mi? — seçeneklerden birini seç</legend>", html)

    def test_pagination_marks_the_current_page(self):
        for i in range(11):
            make_poll(self.author, question=f"Sayfalama sorusu {i}")
        html = self.client.get(reverse("polls:list")).content.decode()
        self.assertIn('class="pagination__info" aria-current="page"', html)

    def test_option_builder_has_a_polite_live_region(self):
        self.client.force_login(self.author)
        html = self.client.get(reverse("polls:create")).content.decode()
        self.assertIn("data-option-status", html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn("announce(", JS_PATH.read_text(encoding="utf-8"))


class RankIsNotOnlyColourTests(TestCase):
    """Sonuç sıralaması renkten bağımsız olarak yazıyla da verilir (renk körleri için)."""

    @classmethod
    def setUpTestData(cls):
        author = make_user()
        cls.poll = make_poll(author, options=("Evet", "Hayır", "Belki"), ends_at=timezone.now() - timedelta(hours=1))
        for _ in range(5):
            cast(cls.poll, 0)
        for _ in range(3):
            cast(cls.poll, 1)
        cast(cls.poll, 2)

    def test_each_option_states_its_place_in_text(self):
        html = self.client.get(self.poll.get_absolute_url()).content.decode()
        self.assertIn("%56 · 5 oy · 1. sıra", html)
        self.assertIn("%33 · 3 oy · 2. sıra", html)
        self.assertIn("%11 · 1 oy · 3. sıra", html)

    def test_bar_label_for_screen_readers_includes_the_place(self):
        html = self.client.get(self.poll.get_absolute_url()).content.decode()
        self.assertIn("Evet: yüzde 56, 5 oy, 1. sırada", html)

    def test_tied_options_share_a_place(self):
        tied = make_poll(make_user("ayse"), ends_at=timezone.now() - timedelta(hours=1))
        cast(tied, 0)
        cast(tied, 1)
        html = self.client.get(tied.get_absolute_url()).content.decode()
        self.assertEqual(html.count("· 1. sıra"), 2)  # görünür metin; ikisi de birinci

    def test_no_rank_text_when_nobody_voted(self):
        empty = make_poll(make_user("can"), ends_at=timezone.now() - timedelta(hours=1))
        html = self.client.get(empty.get_absolute_url()).content.decode()
        self.assertNotIn(". sıra", html)


class MobileAndContrastCssTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = CSS_PATH.read_text(encoding="utf-8")

    def test_touch_targets_are_at_least_44px(self):
        self.assertRegex(self.css, r"\.btn,\s*\.tabs__link\s*\{[^}]*min-height:\s*44px")
        self.assertRegex(self.css, r"\.navbar__brand,\s*\.back-link\s*\{[^}]*min-height:\s*44px")

    def test_navbar_wraps_on_narrow_screens_instead_of_overflowing(self):
        mobile = self.css.split("/* ---------- Faz 7", 1)[1].split("@media (max-width: 480px)", 1)[1]
        self.assertRegex(mobile, r"\.navbar__links\s*\{[^}]*flex-wrap:\s*wrap")
        self.assertRegex(mobile, r"\.navbar__user\s*\{[^}]*flex:\s*1 1 100%")

    def test_text_size_is_not_inflated_by_mobile_browsers(self):
        self.assertIn("-webkit-text-size-adjust: 100%", self.css)

    def test_forced_colors_mode_is_supported(self):
        self.assertIn("@media (forced-colors: active)", self.css)

    def test_messages_and_errors_have_non_colour_icons(self):
        for icon in ('"✓"', '"✕"', '"!"', '"i"'):
            self.assertIn(f"content: {icon}", self.css)

    def test_form_inputs_are_16px_so_ios_does_not_zoom(self):
        self.assertIn("font: inherit", self.css)  # girdiler gövde yazı boyutunu (16px) devralır
        self.assertRegex(self.css, r"html\s*\{\s*font-size:\s*16px")

    def test_viewport_allows_zooming(self):
        base = (CSS_PATH.parents[2] / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertNotIn("user-scalable=no", base)
        self.assertNotIn("maximum-scale", base)
