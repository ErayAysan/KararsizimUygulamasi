"""Admin adresi ortam değişkeniyle değiştirilebilir; eski /admin/ adresi kapanır."""

import importlib

from django.test import TestCase, override_settings
from django.urls import clear_url_caches

import config.urls


def reload_urls():
    clear_url_caches()
    importlib.reload(config.urls)


class AdminUrlTests(TestCase):
    def tearDown(self):
        reload_urls()  # sonraki testler varsayılan adresi görsün

    @override_settings(ROOT_URLCONF="config.urls", ADMIN_URL="admin/")
    def test_default_admin_url_is_admin(self):
        reload_urls()
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)

    @override_settings(ROOT_URLCONF="config.urls", ADMIN_URL="gizli-yol-123/")
    def test_custom_admin_url_replaces_the_default_one(self):
        reload_urls()
        self.assertEqual(self.client.get("/gizli-yol-123/login/").status_code, 200)
        self.assertEqual(self.client.get("/admin/login/").status_code, 404)
        self.assertEqual(self.client.get("/admin/").status_code, 404)

    def test_setting_is_normalised_from_the_environment(self):
        import os
        import subprocess
        import sys

        from django.conf import settings

        code = "import django, os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; from django.conf import settings; print(settings.ADMIN_URL)"
        for raw, expected in (("yonetim", "yonetim/"), ("/yonetim/", "yonetim/"), (" yonetim ", "yonetim/"), ("", "admin/")):
            env = {**os.environ, "DJANGO_ADMIN_URL": raw, "DJANGO_DEBUG": "True"}
            out = subprocess.run([sys.executable, "-c", code], cwd=settings.BASE_DIR, env=env, capture_output=True, text=True)
            self.assertEqual(out.stdout.strip(), expected, out.stderr)
