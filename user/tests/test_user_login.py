import time
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


class UserLoginTests(TestCase):

    def setUp(self):
        self.password = "Passw0rd!"
        self.user = User.objects.create_user(
            email="test@gastronome.com",
            password=self.password,
            display_name="test",
            username="test@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
        )
        self.url = reverse("user:login")

    def _set_captcha_in_session(self, code="ABCD"):
        """
        Seed the current session with a known captcha_code.
        """
        session = self.client.session
        session["captcha_code"] = [code, time.time()]
        session.save()

    def test_login_success(self):
        """
        Test that correct captcha + correct password redirects to profile.
        """
        self._set_captcha_in_session("ABCD")
        response = self.client.post(
            self.url,
            data={
                "email": self.user.email,
                "password": self.password,
                "captcha": "ABCD",
            },
        )
        self.assertRedirects(response, reverse("user:profile"))
        self.assertNotIn("captcha_code", self.client.session)

    def test_login_invalid_captcha(self):
        """
        Test that incorrect captcha input prevents login.
        """
        self._set_captcha_in_session("ABCD")
        response = self.client.post(
            self.url,
            data={
                "email": self.user.email,
                "password": self.password,
                "captcha": "WXYZ",
            },
            follow=True,
        )
        self.assertContains(response, "Invalid captcha")

    def test_login_missing_captcha(self):
        """
        Test that missing captcha input prevents login.
        """
        self._set_captcha_in_session("ABCD")
        response = self.client.post(
            self.url,
            data={
                "email": self.user.email,
                "password": self.password,
            },
            follow=True,
        )
        self.assertContains(response, "Invalid captcha")

    def test_login_wrong_password(self):
        """
        Test that wrong password with correct captcha does not log in.
        """
        self._set_captcha_in_session("ABCD")
        response = self.client.post(
            self.url,
            data={
                "email": self.user.email,
                "password": "WrongPass123",
                "captcha": "ABCD",
            },
            follow=True,
        )
        self.assertContains(response, "Invalid email or password")

    def test_login_nonexistent_user(self):
        """
        Test that login with a non-existent user does not succeed.
        """
        self._set_captcha_in_session("ABCD")
        response = self.client.post(
            self.url,
            data={
                "email": "ghost@gastronome.com",
                "password": "Whatever123",
                "captcha": "ABCD",
            },
            follow=True,
        )
        self.assertContains(response, "Invalid email or password")

    def test_login_get_request(self):
        """
        Test that GET request to login page returns the login template.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "login.html")

    def test_captcha_case_insensitive(self):
        """
        Test that backend converts input to uppercase; mixed case input should also work.
        """
        self._set_captcha_in_session("ABCD")
        response = self.client.post(
            self.url,
            data={
                "email": self.user.email,
                "password": self.password,
                "captcha": "abcd",
            },
        )
        self.assertRedirects(response, reverse("user:profile"))

    def test_captcha_popped_after_first_attempt(self):
        """
        Test that captcha is removed from session after a successful login.
        """
        self._set_captcha_in_session("ABCD")
        self.client.post(
            self.url,
            data={
                "email": self.user.email,
                "password": self.password,
                "captcha": "ABCD",
            },
        )
        response = self.client.post(
            self.url,
            data={
                "email": self.user.email,
                "password": self.password,
                "captcha": "ABCD",
            },
            follow=True,
        )
        self.assertContains(response, "Invalid captcha")

    def test_login_without_setting_captcha_in_session(self):
        """
        User bypasses frontend and sends request directly, without captcha_code in session.
        Test that login fails if captcha_code is not set in session.
        """
        response = self.client.post(
            self.url,
            data={
                "email": self.user.email,
                "password": self.password,
                "captcha": "ABCD",
            },
            follow=True,
        )
        self.assertContains(response, "Invalid captcha")

    def test_login_email_case_insensitive(self):
        """
        Test that login with email in different case works.
        """
        self._set_captcha_in_session()
        resp = self.client.post(
            self.url,
            data={
                "email": self.user.email.upper(),
                "password": self.password,
                "captcha": "ABCD",
            },
        )
        self.assertRedirects(resp, reverse("user:profile"))

    def test_login_after_wrong_password_needs_new_captcha(self):
        """
        Test that after a wrong password attempt, the captcha needs to be re-entered,
        the same captcha string should not work again.
        """
        self._set_captcha_in_session()
        self.client.post(
            self.url,
            data={
                "email": self.user.email,
                "password": "Wrong123!",
                "captcha": "ABCD",
            },
            follow=True,
        )
        resp = self.client.post(
            self.url,
            data={
                "email": self.user.email,
                "password": self.password,
                "captcha": "ABCD",
            },
            follow=True,
        )
        self.assertContains(resp, "Invalid captcha")

    @override_settings(LOAD_TEST=True)
    def test_login_skips_captcha_in_load_test_mode(self):
        """
        Test that when LOAD_TEST=True, the captcha is skipped,
        and the user can log in without providing a captcha.
        """
        resp = self.client.post(
            self.url,
            data={
                "email": self.user.email,
                "password": self.password,
            },
        )
        self.assertRedirects(resp, reverse("user:profile"))
