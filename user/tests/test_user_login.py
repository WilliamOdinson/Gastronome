import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserLoginTests(TestCase):

    def setUp(self):
        self.password = "Passw0rd!"
        self.user = User.objects.create_user(
            email="test@gastronome.com",
            password=self.password,
            display_name="Tester",
            username="test@gastronome.com",   # username field in AbstractUser is still required
            user_id="u12345678901234567890"
        )
        self.url = reverse("user:login")

    def _set_captcha_in_session(self, code="ABCD"):
        """
        Write captcha_code to the current session of the test client.
        The view expects the format: [code, timestamp]
        """
        session = self.client.session
        session["captcha_code"] = [code, time.time()]
        session.save()

    def test_login_success(self):
        """
        Correct captcha + correct password
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
        # After successful login, captcha_code should be popped from session
        self.assertNotIn("captcha_code", self.client.session)

    def test_login_invalid_captcha(self):
        """
        Captcha mismatch => stay on login page with error message
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
        GET request should return 200 and render login template
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "login.html")

    def test_captcha_case_insensitive(self):
        """
        Backend converts input to uppercase; mixed case input should also work
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
        After the first submission, captcha_code is removed from session.
        Resubmitting (e.g., via browser back + resubmit) should fail.
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
        # Second submission: session no longer has captcha_code
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
        User bypasses frontend and sends request directly, without captcha_code in session
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
