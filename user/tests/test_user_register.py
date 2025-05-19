import time
import uuid

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserRegisterTests(TestCase):

    def setUp(self):
        self.url_register = reverse("user:register")
        self.url_verify = reverse("user:verify_email")
        self.url_resend = reverse("user:resend_verification")

        self.email = "test@gastronome.com"
        self.display = "test"
        self.pass1 = "Passw0rd!"
        self.pass2 = self.pass1

    def _set_captcha(self, code="ABCD"):
        session = self.client.session
        session["captcha_code"] = [code, time.time()]
        session.save()

    def _post_register(self, captcha="ABCD", **override):
        data = {
            "email": self.email,
            "display_name": self.display,
            "password1": self.pass1,
            "password2": self.pass2,
            "captcha": captcha,
        }
        data.update(override)
        return self.client.post(self.url_register, data, follow=True)

    def test_get_register_page(self):
        resp = self.client.get(self.url_register)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "register.html")

    def test_register_success_flow(self):
        """
        - Successfully enters verify_email
        - pending_register exists in cache
        - Email has been sent
        - pending_email is saved in session
        """
        self._set_captcha()
        resp = self._post_register()
        self.assertRedirects(resp, self.url_verify)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.email, mail.outbox[0].to)

        pending = cache.get(f"pending_register:{self.email}")
        self.assertIsNotNone(pending)
        self.assertEqual(pending["display_name"], self.display)

        self.assertEqual(self.client.session["pending_email"], self.email)

    def test_register_invalid_captcha(self):
        self._set_captcha("ABCD")
        resp = self._post_register(captcha="WXYZ")
        self.assertContains(resp, "Invalid captcha")

    def test_register_password_mismatch(self):
        self._set_captcha()
        self.pass2 = "Different1!"
        resp = self._post_register()
        self.assertContains(resp, "Passwords do not match.")

    def test_register_missing_fields(self):
        self._set_captcha()
        resp = self.client.post(
            self.url_register,
            data={"email": "", "display_name": "", "captcha": "ABCD"},
            follow=True,
        )
        self.assertContains(resp, "All fields are required.")

    def test_register_weak_password_rejected(self):
        """
        Password does not meet complexity requirements
        """
        self.pass1 = self.pass2 = "abc"
        self._set_captcha()
        resp = self._post_register()
        self.assertContains(resp, "Password must be at least 8 characters")

    def test_register_email_already_exists(self):
        """Email already exists in the database"""
        # Create an existing user first
        User.objects.create_user(
            email=self.email,
            password="Another123!",
            display_name="Someone",
            username=self.email, user_id="u" + uuid.uuid4().hex[:21],
        )
        self._set_captcha()
        resp = self._post_register()
        self.assertContains(resp, "already registered")

    def test_register_overwrites_existing_pending_cache(self):
        """Second submission refreshes the verification_code"""
        self._set_captcha()
        self._post_register()
        first_code = cache.get(f"pending_register:{self.email}")["verification_code"]

        # Reset captcha and resubmit
        self._set_captcha()
        resp = self._post_register()
        self.assertRedirects(resp, self.url_verify)
        second_code = cache.get(f"pending_register:{self.email}")["verification_code"]
        self.assertNotEqual(first_code, second_code)

    def test_verify_email_success_creates_user(self):
        """Full flow: register -> verify -> auto login"""
        # Register first
        self._set_captcha()
        self._post_register()
        pending = cache.get(f"pending_register:{self.email}")
        code = pending["verification_code"]

        # Submit verification code
        resp = self.client.post(self.url_verify, {"code": code}, follow=True)
        self.assertRedirects(resp, reverse("core:index"))

        # User has been created and logged in
        self.assertTrue(User.objects.filter(email=self.email).exists())
        self.assertIn("_auth_user_id", self.client.session)

        # Cache cleared
        self.assertIsNone(cache.get(f"pending_register:{self.email}"))

    def test_verify_email_invalid_code(self):
        self._set_captcha()
        self._post_register()
        resp = self.client.post(self.url_verify, {"code": "000000"}, follow=True)
        self.assertContains(resp, "Invalid verification code.")

    def test_resend_verification_updates_code_and_sends_mail(self):
        # Complete the first registration to get the old code
        self._set_captcha()
        self._post_register()
        pending = cache.get(f"pending_register:{self.email}")
        old_code = pending["verification_code"]

        mail.outbox = []
        resp = self.client.get(self.url_resend, follow=True)
        self.assertRedirects(resp, self.url_verify)
        self.assertEqual(len(mail.outbox), 1)

        new_code = cache.get(f"pending_register:{self.email}")["verification_code"]

        self.assertNotEqual(old_code, new_code)
        self.assertIn(new_code, mail.outbox[0].body)
