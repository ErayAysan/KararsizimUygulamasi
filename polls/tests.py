from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_renders(self):
        response = self.client.get(reverse("polls:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kararsızım")
        self.assertContains(response, 'lang="tr"')
