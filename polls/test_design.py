"""Faz 5: kontrast (WCAG AA), hata sayfaları, sayfa başlıkları ve erişilebilirlik testleri."""

import re
from unittest import mock

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from .tests import make_poll, make_user

CSS_PATH = settings.BASE_DIR / "static" / "css" / "style.css"
JS_PATH = settings.BASE_DIR / "static" / "js" / "main.js"


def load_palette():
    css = CSS_PATH.read_text(encoding="utf-8")
    root = re.search(r":root\s*\{(.*?)\}", css, re.S).group(1)
    palette = {m.group(1): m.group(2) for m in re.finditer(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})", root)}
    palette["white"] = "#FFFFFF"
    return palette


def luminance(hex_color):
    h = hex_color.lstrip("#")
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


OPTIONS = [f"opt-{i}" for i in range(1, 6)]

# (ön plan, arka plan) — normal metin için en az 4,5:1 (WCAG AA)
TEXT_PAIRS = [
    ("text", "bg"), ("text", "surface"), ("text", "primary-soft"),
    ("text-muted", "bg"), ("text-muted", "surface"),
    ("white", "primary"), ("white", "primary-hover"),
    ("primary", "bg"), ("primary", "surface"), ("primary", "primary-soft"),
    ("primary-hover", "primary-soft"), ("primary-hover", "border"),
    ("success", "primary-soft"), ("success", "bg"), ("success", "surface"),
    ("error", "surface"), ("error", "primary-soft"), ("error", "bg"),
] + [("text", option) for option in OPTIONS]

# Arayüz bileşenleri (kenarlık, odak halkası, seçili durum) için en az 3:1 (WCAG 1.4.11)
UI_PAIRS = [
    ("border-strong", "surface"), ("border-strong", "bg"),
    ("text-muted", "surface"),  # sonuç çubuğu kenarlığı
    ("primary", "surface"), ("primary", "bg"),  # odak halkası, seçili kenarlık
] + [("border-strong", option) for option in OPTIONS] + [("primary", option) for option in OPTIONS]


class ContrastTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.palette = load_palette()

    def test_palette_defines_every_color_used_in_the_checks(self):
        needed = {name for pair in TEXT_PAIRS + UI_PAIRS for name in pair}
        self.assertFalse(needed - set(self.palette), needed - set(self.palette))

    def test_text_pairs_meet_wcag_aa(self):
        for fg, bg in TEXT_PAIRS:
            ratio = contrast(self.palette[fg], self.palette[bg])
            self.assertGreaterEqual(ratio, 4.5, f"{fg} / {bg} = {ratio:.2f}")

    def test_ui_component_pairs_meet_three_to_one(self):
        for fg, bg in UI_PAIRS:
            ratio = contrast(self.palette[fg], self.palette[bg])
            self.assertGreaterEqual(ratio, 3.0, f"{fg} / {bg} = {ratio:.2f}")

    def test_decorative_accents_are_never_used_as_text_color(self):
        css = CSS_PATH.read_text(encoding="utf-8")
        for accent in ("--accent-coral", "--accent-yellow"):
            self.assertNotRegex(css, rf"(?<!-)color:\s*var\({accent}\)")


class StaticAssetTests(SimpleTestCase):
    def test_css_respects_reduced_motion_and_animates_result_bars(self):
        css = CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn("@keyframes bar-fill", css)
        self.assertIn(":focus-visible", css)

    def test_js_guards_double_submit(self):
        js = JS_PATH.read_text(encoding="utf-8")
        self.assertIn("data-submitting", js)
        self.assertIn("pageshow", js)  # geri/ileri önbelleğinde butonlar yeniden etkinleşir


class ErrorPageTests(TestCase):
    def test_404_is_a_friendly_turkish_page_with_navigation(self):
        response = self.client.get("/olmayan/bir/adres/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Bu sayfayı bulamadık", status_code=404)
        self.assertContains(response, "Ana sayfaya dön", status_code=404)
        self.assertContains(response, 'lang="tr"', status_code=404)
        self.assertContains(response, "<title>Sayfa bulunamadı · Kararsızım</title>", status_code=404)

    def test_poll_404_uses_the_same_page(self):
        response = self.client.get("/anket/zzzzzzzzzz/")
        self.assertContains(response, "Bu sayfayı bulamadık", status_code=404)

    def test_500_is_a_standalone_turkish_page(self):
        client = Client(raise_request_exception=False)
        with mock.patch("polls.views.render", side_effect=RuntimeError("boom")):
            with self.assertLogs("django.request", level="ERROR"):
                response = client.get(reverse("polls:list"))
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Bir şeyler ters gitti", status_code=500)
        self.assertContains(response, 'lang="tr"', status_code=500)
        self.assertNotContains(response, "/static/", status_code=500)  # statik dosyaya bağımlı değil

    def test_csrf_failure_page_is_turkish(self):
        response = Client(enforce_csrf_checks=True).post(reverse("accounts:login"), {"username": "a@b.co", "password": "x"})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Sayfanın süresi dolmuş olabilir", status_code=403)


class PageMetadataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.poll = make_poll(cls.user)

    def get_all(self):
        member = Client()
        member.force_login(self.user)
        guest = Client()
        return {
            "list": guest.get(reverse("polls:list")),
            "detail": guest.get(self.poll.get_absolute_url()),
            "create": member.get(reverse("polls:create")),
            "login": guest.get(reverse("accounts:login")),
            "register": guest.get(reverse("accounts:register")),
        }

    def test_every_page_has_title_description_theme_color_and_lang(self):
        for name, response in self.get_all().items():
            html = response.content.decode()
            self.assertEqual(response.status_code, 200, name)
            self.assertRegex(html, r"<title>[^<]+</title>", name)
            self.assertRegex(html, r'<meta name="description" content="[^"]{20,}">', name)
            self.assertIn('<meta name="theme-color"', html, name)
            self.assertIn('<html lang="tr">', html, name)

    def test_titles_are_unique_per_page_type(self):
        titles = {
            name: re.search(r"<title>([^<]+)</title>", r.content.decode()).group(1) for name, r in self.get_all().items()
        }
        self.assertEqual(len(set(titles.values())), len(titles), titles)

    def test_descriptions_are_distinct_per_page_type(self):
        descriptions = {
            name: re.search(r'<meta name="description" content="([^"]*)"', r.content.decode()).group(1)
            for name, r in self.get_all().items()
        }
        self.assertEqual(len(set(descriptions.values())), len(descriptions), descriptions)

    def test_paginated_list_title_mentions_the_page(self):
        author = make_user("yazar")
        for i in range(11):
            make_poll(author, question=f"Sayfalama başlık sorusu {i:02d}?")
        html = self.client.get(reverse("polls:list"), {"page": 2}).content.decode()
        self.assertIn("<title>Anketler · Sayfa 2 · Kararsızım</title>", html)

    def test_poll_page_title_is_the_question(self):
        html = self.client.get(self.poll.get_absolute_url()).content.decode()
        self.assertIn(f"<title>{self.poll.question} · Kararsızım</title>", html)


class AccessibilityStructureTests(TestCase):
    def test_skip_link_points_to_the_main_landmark(self):
        html = self.client.get(reverse("polls:list")).content.decode()
        self.assertIn('<a class="skip-link" href="#icerik">', html)
        self.assertRegex(html, r'<main[^>]*id="icerik"')
        self.assertLess(html.index("skip-link"), html.index("<nav"))  # odak sırasında en başta

    def test_landmarks_and_labels(self):
        html = self.client.get(reverse("polls:list")).content.decode()
        self.assertIn("<header", html)
        self.assertIn('<nav class="navbar__inner container" aria-label="Ana gezinme">', html)
        self.assertEqual(html.count("<main"), 1)
        self.assertEqual(html.count("<h1"), 1)

    def test_every_form_control_has_a_label(self):
        user = make_user()
        poll = make_poll(user)
        self.client.force_login(user)
        pages = [
            Client().get(reverse("accounts:login")),
            Client().get(reverse("accounts:register")),
            self.client.get(reverse("polls:create")),
            Client().get(poll.get_absolute_url()),
        ]
        for response in pages:
            html = response.content.decode()
            ids = re.findall(r'<input(?![^>]*type="(?:hidden|submit)")[^>]*\bid="([^"]+)"', html)
            self.assertTrue(ids)
            for control_id in ids:
                self.assertRegex(html, rf'<label[^>]*for="{re.escape(control_id)}"', control_id)

    def test_vote_options_are_real_radio_inputs_with_labels(self):
        poll = make_poll(make_user())
        html = self.client.get(poll.get_absolute_url()).content.decode()
        self.assertEqual(len(re.findall(r'<input type="radio"', html)), 2)
        self.assertIn('<legend class="visually-hidden">Seçenekler</legend>', html)

    def test_error_messages_are_announced(self):
        user = make_user()
        poll = make_poll(user)
        self.client.get(poll.get_absolute_url())  # misafir çerezi
        response = self.client.post(reverse("polls:vote", args=[poll.public_id]), {"option": "9"}, follow=True)
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, "Lütfen bir seçenek seç.")

    def test_result_bars_expose_text_alternatives(self):
        author = make_user("yazar")
        poll = make_poll(author)
        self.client.force_login(author)
        html = self.client.get(poll.get_absolute_url()).content.decode()
        self.assertRegex(html, r'class="result__bar" role="img" aria-label="[^"]+: yüzde \d+, \d+ oy"')

