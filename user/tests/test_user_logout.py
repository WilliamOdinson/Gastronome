import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserLogoutTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@gastronome.com",
            password="Passw0rd!",
            display_name="test",
            username="test@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
        )
        self.logout_url = reverse("user:logout")
        self.home_url = reverse("core:index")

    def _login(self):
        """
        Force login user using built-in test client
        """
        self.client.force_login(self.user)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_via_post(self):
        """
        Test that logging out via POST request redirects to home and clears session.
        """
        self._login()
        response = self.client.post(self.logout_url)
        self.assertRedirects(response, self.home_url)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_via_get_not_allowed(self):
        """
        Test that logging out via GET request returns 405 Method Not Allowed.
        """
        self._login()
        resp = self.client.get(self.logout_url)
        self.assertEqual(resp.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_with_extra_session_keys(self):
        """
        Test that logging out clears session keys other than _auth_user_id.
        """
        self._login()
        session = self.client.session
        session["pending_email"] = "someone@gastronome.com"
        session.save()
        self.client.post(self.logout_url)
        self.assertNotIn("pending_email", self.client.session)

    def test_logout_when_anonymous(self):
        """
        Test that logging out when anonymous redirects to home.
        """
        self.client.logout()  # Ensure we start as anonymous
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.session.keys(), set())
        response = self.client.post(self.logout_url)
        self.assertRedirects(response, self.home_url)

    def test_logout_get_anonymous_not_allowed(self):
        """
        Test that GET request to logout when anonymous returns 405.
        """
        resp = self.client.get(self.logout_url)
        self.assertEqual(resp.status_code, 405)
