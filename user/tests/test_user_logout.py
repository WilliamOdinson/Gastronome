from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserLogoutTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="logout@gastronome.com",
            password="Passw0rd!",
            display_name="LogoutUser",
            username="logout@gastronome.com",
            user_id="logout1234567890123456",
        )
        self.logout_url = reverse("user:logout")
        self.home_url = reverse("core:index")

    def _login(self):
        """
        Force login user using built-in test client
        """
        self.client.force_login(self.user)
        self.assertIn("_auth_user_id", self.client.session)  # sanity‑check

    def test_logout_via_post(self):
        """
        POST /logout/ should redirect to homepage and clear session
        """
        self._login()
        response = self.client.post(self.logout_url)
        self.assertRedirects(response, self.home_url)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_via_get_not_allowed(self):
        self._login()
        resp = self.client.get(self.logout_url)
        self.assertEqual(resp.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)


    def test_logout_with_extra_session_keys(self):
        """
        Custom session data should also be cleared
        """
        self._login()
        session = self.client.session
        session["pending_email"] = "someone@gastronome.com"
        session.save()

        self.client.post(self.logout_url)
        self.assertNotIn("pending_email", self.client.session)

    def test_logout_when_anonymous(self):
        """
        Anonymous users visiting /logout/ should still receive the same redirect
        """
        response = self.client.post(self.logout_url)
        self.assertRedirects(response, self.home_url)
