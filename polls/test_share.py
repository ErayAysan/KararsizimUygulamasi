"""Faz 7: paylaşım bağlantısı ve Open Graph / Twitter önizleme etiketleri."""

import re
import struct
from datetime import timedelta
from html import unescape
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .test_design import JS_PATH
from .test_voting import cast
from .tests import make_poll, make_user


def meta(html, key):
    """`property` ya da `name` değeri `key` olan meta etiketinin içeriği."""
    match = re.search(rf'<meta (?:property|name)="{re.escape(key)}" content="([^"]*)"', html)
    return unescape(match.group(1)) if match else None


class OpenGraphTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.poll = make_poll(cls.author, question="Hafta sonu sinemaya mı gitsem?", options=("Sinema", "Müze", "Ev"))

    def html(self, poll=None):
        return Client().get((poll or self.poll).get_absolute_url()).content.decode()

    def test_poll_page_has_title_url_and_image(self):
        html = self.html()
        self.assertEqual(meta(html, "og:title"), "Hafta sonu sinemaya mı gitsem?")
        self.assertEqual(meta(html, "og:type"), "website")
        self.assertEqual(meta(html, "og:site_name"), "Kararsızım")
        self.assertEqual(meta(html, "og:url"), f"http://testserver{self.poll.get_absolute_url()}")
        self.assertTrue(meta(html, "og:image").startswith("http://testserver/static/img/og-image"))
        self.assertEqual(meta(html, "twitter:card"), "summary_large_image")
        self.assertIn(f'<link rel="canonical" href="http://testserver{self.poll.get_absolute_url()}">', html)

    def test_description_lists_the_options_and_the_author(self):
        description = meta(self.html(), "og:description")
        self.assertIn("@ahmet", description)
        self.assertIn("Sinema / Müze / Ev", description)
        self.assertIn("Sen ne dersin?", description)

    def test_description_never_leaks_results(self):
        poll = make_poll(self.author, question="Sonuç sızıntısı sorusu", options=("A", "B"))
        for _ in range(7):
            cast(poll, 0)
        description = meta(self.html(poll), "og:description")
        self.assertNotRegex(description, r"\d")  # oy sayısı ya da yüzde yok
        self.assertNotIn("%", description)
        self.assertNotIn("🏆", description)

    def test_closed_poll_description_says_it_is_over(self):
        closed = make_poll(self.author, question="Süresi bitmiş soru", ends_at=timezone.now() - timedelta(hours=1))
        description = meta(self.html(closed), "og:description")
        self.assertIn("Süresi doldu", description)
        self.assertNotIn("Sen ne dersin?", description)

    def test_description_is_capped_at_200_characters(self):
        poll = make_poll(self.author, question="Çok seçenekli soru", options=("x" * 100, "y" * 100, "z" * 100))
        self.assertLessEqual(len(meta(self.html(poll), "og:description")), 200)

    def test_question_with_quotes_and_markup_is_escaped(self):
        poll = make_poll(self.author, question='"Tırnak" <script>alert(1)</script> sorusu?')
        html = self.html(poll)
        self.assertNotIn("<script>alert(1)", html)
        self.assertEqual(meta(html, "og:title"), '"Tırnak" <script>alert(1)</script> sorusu?')

    def test_home_page_has_default_preview_tags(self):
        html = self.client.get(reverse("polls:list")).content.decode()
        self.assertIn("Kararsızım", meta(html, "og:title"))
        self.assertIn("anket aç", meta(html, "og:description"))
        self.assertTrue(meta(html, "og:image"))

    def test_preview_never_contains_email_or_numeric_id(self):
        html = self.html()
        for key in ("og:title", "og:description", "og:url"):
            value = meta(html, key)
            self.assertNotIn(self.author.email, value)
            self.assertNotIn(f"/anket/{self.poll.pk}/", value)

    def test_create_and_delete_pages_are_not_indexed(self):
        self.client.force_login(self.author)
        for url in (reverse("polls:create"), reverse("polls:delete", args=[self.poll.public_id])):
            self.assertIn('<meta name="robots" content="noindex">', self.client.get(url).content.decode())


class SharePanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.poll = make_poll(cls.author, question="Hangi telefonu alsam?")

    def html(self):
        return Client().get(self.poll.get_absolute_url()).content.decode()

    def test_link_box_works_without_javascript(self):
        html = self.html()
        self.assertIn(f'value="http://testserver{self.poll.get_absolute_url()}"', html)
        self.assertIn("readonly", html)
        self.assertRegex(html, r'<label for="share-url" class="visually-hidden">Anket bağlantısı</label>')

    def test_js_only_buttons_start_hidden(self):
        html = self.html()
        self.assertRegex(html, r"data-copy hidden")
        self.assertRegex(html, r"data-native-share hidden")

    def test_whatsapp_link_carries_question_and_url(self):
        html = self.html()
        href = unescape(re.search(r'href="(https://wa\.me/\?text=[^"]+)"', html).group(1))
        text = parse_qs(urlparse(href).query)["text"][0]
        self.assertIn("Hangi telefonu alsam?", text)
        self.assertIn(f"http://testserver{self.poll.get_absolute_url()}", text)

    def test_external_link_is_safe_and_announced(self):
        html = self.html()
        self.assertIn('target="_blank" rel="noopener noreferrer"', html)
        self.assertIn("yeni sekmede açılır", html)

    def test_status_is_a_polite_live_region(self):
        self.assertIn('role="status" aria-live="polite" data-share-status', self.html())

    def test_panel_is_a_named_region(self):
        html = self.html()
        self.assertIn('aria-labelledby="share-title"', html)
        self.assertIn('id="share-title"', html)

    def test_share_url_has_only_the_public_code(self):
        html = self.html()
        self.assertNotIn(f"/anket/{self.poll.pk}/", html)

    def test_panel_is_also_shown_on_closed_polls(self):
        closed = make_poll(self.author, ends_at=timezone.now() - timedelta(hours=1))
        self.assertContains(Client().get(closed.get_absolute_url()), "Anketi paylaş")


class ShareScriptTests(SimpleTestCase):
    def test_script_uses_native_share_and_clipboard_with_fallback(self):
        js = JS_PATH.read_text(encoding="utf-8")
        self.assertIn("navigator.share", js)
        self.assertIn("navigator.clipboard.writeText", js)
        self.assertIn('execCommand("copy")', js)  # eski tarayıcılar için yedek

    def test_script_only_reveals_native_share_when_supported(self):
        js = JS_PATH.read_text(encoding="utf-8")
        self.assertRegex(js, r"if \(navigator\.share\) \{\s*shareButton\.hidden = false")


class OgImageTests(SimpleTestCase):
    path = settings.BASE_DIR / "static" / "img" / "og-image.jpg"

    def dimensions(self):
        data = self.path.read_bytes()
        i = 2
        while i < len(data):
            marker = data[i + 1]
            length = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC2):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return width, height
            i += 2 + length
        self.fail("JPEG boyutu okunamadı")

    def test_image_exists_and_is_a_jpeg(self):
        data = self.path.read_bytes()
        self.assertEqual(data[:3], b"\xff\xd8\xff")
        self.assertLess(len(data), 5 * 1024 * 1024)  # önizleme görselleri 5 MB'ı geçmemeli

    def test_image_is_large_enough_and_has_the_wide_card_ratio(self):
        width, height = self.dimensions()
        self.assertGreaterEqual(width, 600)  # büyük önizleme kartı için asgari boyut
        self.assertGreaterEqual(height, 315)
        self.assertAlmostEqual(width / height, 1.91, delta=0.05)

    def test_declared_dimensions_match_the_file(self):
        width, height = self.dimensions()
        base = (settings.BASE_DIR / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn(f'og:image:width" content="{width}"', base)
        self.assertIn(f'og:image:height" content="{height}"', base)
