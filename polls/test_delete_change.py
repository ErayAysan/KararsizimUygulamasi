"""Faz 7: anket silme (yalnızca sahibi) ve oy değiştirme seçeneği."""

from datetime import timedelta

from django.http import QueryDict
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import PollForm
from .models import Poll, Vote
from .test_voting import cast, messages_of, visit
from .tests import make_poll, make_user


def vote_url(poll):
    return reverse("polls:vote", args=[poll.public_id])


def delete_url(poll):
    return reverse("polls:delete", args=[poll.public_id])


class PollDeleteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.other = make_user("ayse")

    def setUp(self):
        self.poll = make_poll(self.author)
        cast(self.poll, 0)

    def test_owner_sees_confirmation_page_with_vote_count(self):
        self.client.force_login(self.author)
        response = self.client.get(delete_url(self.poll))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "geri alınamaz")
        self.assertContains(response, "<strong>1</strong> oy")
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())  # GET silmez

    def test_owner_can_delete_with_post_and_votes_go_too(self):
        self.client.force_login(self.author)
        response = self.client.post(delete_url(self.poll))
        self.assertRedirects(response, reverse("polls:list"))
        self.assertFalse(Poll.objects.exists())
        self.assertFalse(Vote.objects.exists())
        self.assertIn("Anketin silindi.", messages_of(response))

    def test_other_member_gets_404_and_poll_survives(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(delete_url(self.poll)).status_code, 404)
        self.assertEqual(self.client.post(delete_url(self.poll)).status_code, 404)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_guest_is_sent_to_login_and_poll_survives(self):
        response = Client().post(delete_url(self.poll))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_delete_icon_is_shown_only_to_the_owner(self):
        url = delete_url(self.poll)
        self.client.force_login(self.author)
        self.assertContains(self.client.get(self.poll.get_absolute_url()), url)
        self.assertContains(self.client.get(reverse("polls:list")), url)
        for client in (Client(), self._login(self.other)):
            self.assertNotContains(client.get(self.poll.get_absolute_url()), url)
            self.assertNotContains(client.get(reverse("polls:list")), url)

    def _login(self, user):
        client = Client()
        client.force_login(user)
        return client

    def test_delete_icon_has_an_accessible_name(self):
        self.client.force_login(self.author)
        html = self.client.get(self.poll.get_absolute_url()).content.decode()
        self.assertIn('<span class="visually-hidden">Anketi sil</span>', html)
        self.assertIn('title="Anketi sil"', html)

    def test_get_is_safe_no_csrf_bypass(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.author)
        response = client.post(delete_url(self.poll))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_confirmation_page_has_no_numeric_ids(self):
        self.client.force_login(self.author)
        html = self.client.get(delete_url(self.poll)).content.decode()
        self.assertNotIn(f"/anket/{self.poll.pk}/", html)


class VoteChangeFormTests(TestCase):
    def build(self, value=None):
        data = QueryDict(mutable=True)
        data["question"] = "Bugün sinemaya mı gitsem?"
        data.setlist("option", ["Sinema", "Müze"])
        if value is not None:
            data["vote_change"] = value
        form = PollForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        return form.save(author=make_user())

    def test_default_is_no_change(self):
        self.assertFalse(self.build().allow_vote_change)

    def test_no_means_no_change(self):
        self.assertFalse(self.build("0").allow_vote_change)

    def test_yes_allows_change(self):
        self.assertTrue(self.build("1").allow_vote_change)

    def test_unknown_value_is_rejected(self):
        data = QueryDict(mutable=True)
        data["question"] = "Bugün sinemaya mı gitsem?"
        data.setlist("option", ["Sinema", "Müze"])
        data["vote_change"] = "belki"
        self.assertFalse(PollForm(data).is_valid())

    def test_create_page_has_a_yes_no_choice_defaulting_to_no(self):
        self.client.force_login(make_user("deneme"))
        html = self.client.get(reverse("polls:create")).content.decode()
        self.assertIn("Oy değiştirme", html)
        self.assertIn('value="0" id="id_vote_change_0" checked', html)
        self.assertIn('value="1" id="id_vote_change_1"', html)
        self.assertIn(">Evet</label>", html)
        self.assertIn(">Hayır</label>", html)


class ChangingYourVoteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()

    def make(self, allow, **extra):
        return make_poll(self.author, options=("Evet", "Hayır", "Belki"), allow_vote_change=allow, **extra)

    def test_member_can_change_vote_when_allowed(self):
        poll = self.make(True)
        voter = make_user("ayse")
        self.client.force_login(voter)
        self.client.post(vote_url(poll), {"option": "0"})
        response = self.client.post(vote_url(poll), {"option": "2"})
        self.assertEqual(Vote.objects.filter(poll=poll).count(), 1)
        self.assertEqual(Vote.objects.get(poll=poll).option.order, 2)
        self.assertIn("Oyun değiştirildi. 🔄", messages_of(response))

    def test_guest_can_change_vote_when_allowed(self):
        poll = self.make(True)
        client = Client()
        visit(client, poll)
        client.post(vote_url(poll), {"option": "0"})
        client.post(vote_url(poll), {"option": "1"})
        self.assertEqual(Vote.objects.filter(poll=poll).count(), 1)
        self.assertEqual(Vote.objects.get(poll=poll).option.order, 1)

    def test_change_is_refused_when_not_allowed(self):
        poll = self.make(False)
        self.client.force_login(make_user("ayse"))
        self.client.post(vote_url(poll), {"option": "0"})
        response = self.client.post(vote_url(poll), {"option": "2"})
        self.assertEqual(Vote.objects.get(poll=poll).option.order, 0)
        self.assertIn("Bu ankete zaten oy verdin.", messages_of(response))

    def test_choosing_the_same_option_changes_nothing(self):
        poll = self.make(True)
        self.client.force_login(make_user("ayse"))
        self.client.post(vote_url(poll), {"option": "1"})
        response = self.client.post(vote_url(poll), {"option": "1"})
        self.assertEqual(Vote.objects.filter(poll=poll).count(), 1)
        self.assertIn("Oyun zaten bu seçenekte.", messages_of(response))

    def test_change_is_refused_after_the_deadline(self):
        poll = self.make(True, ends_at=timezone.now() + timedelta(hours=1))
        voter = make_user("ayse")
        self.client.force_login(voter)
        self.client.post(vote_url(poll), {"option": "0"})
        Poll.objects.filter(pk=poll.pk).update(ends_at=timezone.now() - timedelta(minutes=1))
        self.client.post(vote_url(poll), {"option": "2"})
        self.assertEqual(Vote.objects.get(poll=poll).option.order, 0)

    def test_change_never_creates_a_second_vote_and_totals_stay_correct(self):
        poll = self.make(True)
        for i in range(3):
            cast(poll, 0)
        self.client.force_login(make_user("ayse"))
        self.client.post(vote_url(poll), {"option": "0"})
        self.client.post(vote_url(poll), {"option": "1"})
        self.client.post(vote_url(poll), {"option": "2"})
        self.assertEqual(Vote.objects.filter(poll=poll).count(), 4)
        self.assertEqual(Vote.objects.filter(poll=poll, option__order=0).count(), 3)

    def test_changing_with_a_bad_option_keeps_the_old_vote(self):
        poll = self.make(True)
        self.client.force_login(make_user("ayse"))
        self.client.post(vote_url(poll), {"option": "1"})
        self.client.post(vote_url(poll), {"option": "9"})
        self.assertEqual(Vote.objects.get(poll=poll).option.order, 1)

    def test_detail_offers_a_change_form_with_the_current_choice_checked(self):
        poll = self.make(True)
        self.client.force_login(make_user("ayse"))
        self.client.post(vote_url(poll), {"option": "1"})
        html = self.client.get(poll.get_absolute_url()).content.decode()
        self.assertIn("Oyumu Değiştir", html)
        self.assertIn('id="option-1" value="1" checked', html)
        self.assertNotIn("Oyunu verdin, teşekkürler", html)

    def test_detail_has_no_change_form_when_not_allowed(self):
        poll = self.make(False)
        self.client.force_login(make_user("ayse"))
        self.client.post(vote_url(poll), {"option": "1"})
        html = self.client.get(poll.get_absolute_url()).content.decode()
        self.assertNotIn("Oyumu Değiştir", html)
        self.assertIn("Oyunu verdin, teşekkürler", html)

    def test_closed_poll_has_no_change_form(self):
        poll = self.make(True, ends_at=timezone.now() - timedelta(hours=1))
        html = Client().get(poll.get_absolute_url()).content.decode()
        self.assertNotIn("Oyumu Değiştir", html)

    def test_icon_above_the_poll_tells_whether_votes_can_be_changed(self):
        yes = self.make(True)
        no = self.make(False)
        yes_html = Client().get(yes.get_absolute_url()).content.decode()
        no_html = Client().get(no.get_absolute_url()).content.decode()
        self.assertIn("Oy değiştirilebilir", yes_html)
        self.assertIn("🔄", yes_html)
        self.assertIn("Oy değiştirilemez", no_html)
        self.assertNotIn("Oy değiştirilebilir", no_html)

    def test_list_card_marks_polls_that_allow_changes(self):
        self.make(True)
        html = Client().get(reverse("polls:list")).content.decode()
        self.assertIn("Oy değiştirilebilir", html)

    def test_non_voter_still_sees_normal_vote_form_on_changeable_poll(self):
        poll = self.make(True)
        html = Client().get(poll.get_absolute_url()).content.decode()
        self.assertIn("Oyumu Ver", html)
        self.assertNotIn("Oyumu Değiştir", html)
