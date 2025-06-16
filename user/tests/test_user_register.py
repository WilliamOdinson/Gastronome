import time
import uuid
from importlib import reload

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse


FERNET_KEY = "tbEyG_pnHQBeT9XmsiflMK_IgDMoW6ciBdfb2AwKVxU="

User = get_user_model()


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    FERNET_KEY=FERNET_KEY,
)
class UserRegisterTests(TestCase):

    def setUp(self):
        self.url_register = reverse("user:register")
        self.url_verify = reverse("user:verify_email")
        self.url_resend = reverse("user:resend_verification")

        self.email = "test@gastronome.com"
        self.display = "test"
        self.pass1 = "Passw0rd!"
        self.pass2 = self.pass1

        from user import tasks
        tasks.FERNET = Fernet(settings.FERNET_KEY.encode())

    def _set_captcha(self, code="ABCD"):
        sess = self.client.session
        sess["captcha_code"] = [code, time.time()]
        sess.save()

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
        """
        Test that the registration page loads correctly and uses the right template.
        """
        resp = self.client.get(self.url_register)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "register.html")

    def test_register_success_flow(self):
        """
        Test that a successful registration:
            1. Sets the captcha in session.
            2. Posts the registration data.
            3. Redirects to the verification page.
            4. Sends a verification email.
            5. Stores pending registration in cache.
            6. Sets pending email in session.
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
        """
        Test that an invalid captcha input returns an error message.
        """
        self._set_captcha("ABCD")
        resp = self._post_register(captcha="WXYZ")
        self.assertContains(resp, "Invalid captcha")

    def test_register_password_mismatch(self):
        """
        Test that mismatched passwords return an error message.
        """
        self._set_captcha()
        self.pass2 = "Different1!"
        resp = self._post_register()
        self.assertContains(resp, "Passwords do not match.")

    def test_register_missing_fields(self):
        """
        Test that missing required fields return an error message.
        """
        self._set_captcha()
        resp = self.client.post(
            self.url_register,
            data={"email": "", "display_name": "", "captcha": "ABCD"},
            follow=True,
        )
        self.assertContains(resp, "All fields are required.")

    def test_register_weak_password_rejected(self):
        """
        Test that weak passwords are rejected.
        """
        self.pass1 = self.pass2 = "abc"
        self._set_captcha()
        resp = self._post_register()
        self.assertContains(resp, "Password must be at least 8 characters")

    def test_register_email_already_exists(self):
        """
        Test that registering with an existing email returns an error message.
        """
        User.objects.create_user(
            email=self.email,
            password="Another123!",
            display_name="Someone",
            username=self.email,
            user_id="u" + uuid.uuid4().hex[:21],
        )
        self._set_captcha()
        resp = self._post_register()
        self.assertContains(resp, "already registered")

    def test_register_overwrites_existing_pending_cache(self):
        """
        Test that registering again with the same email overwrites the existing
        pending registration cache entry.
        """
        self._set_captcha()
        self._post_register()
        first_code = cache.get(f"pending_register:{self.email}")["verification_code"]
        self._set_captcha()
        self._post_register()
        second_code = cache.get(f"pending_register:{self.email}")["verification_code"]
        self.assertNotEqual(first_code, second_code)

    def test_verify_email_success_creates_user(self):
        """
        Test that verifying email with the correct code creates the user,
        logs them in, and clears the pending registration cache.
        """
        self._set_captcha()
        self._post_register()
        code = cache.get(f"pending_register:{self.email}")["verification_code"]
        resp = self.client.post(self.url_verify, {"code": code}, follow=True)
        self.assertRedirects(resp, reverse("core:index"))
        self.assertTrue(User.objects.filter(email=self.email).exists())
        self.assertIn("_auth_user_id", self.client.session)
        self.assertIsNone(cache.get(f"pending_register:{self.email}"))

    def test_verify_email_invalid_code(self):
        """
        Test that verifying email with an invalid code returns an error message
        and does not create the user.
        """
        self._set_captcha()
        self._post_register()
        resp = self.client.post(self.url_verify, {"code": "000000"}, follow=True)
        self.assertContains(resp, "Invalid verification code.")

    def test_resend_verification_updates_code_and_sends_mail(self):
        """
        Test that resending verification updates the code in cache,
        sends a new email, and does not create a new user.
        """
        self._set_captcha()
        self._post_register()
        old = cache.get(f"pending_register:{self.email}")["verification_code"]
        mail.outbox = []
        self.client.get(self.url_resend, follow=True)
        new = cache.get(f"pending_register:{self.email}")["verification_code"]
        self.assertNotEqual(old, new)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(new, mail.outbox[0].body)

    def test_register_email_case_insensitive_uniqueness(self):
        """
        Test that registering with an email that differs only in case
        is treated as a duplicate and returns an error message.
        """
        User.objects.create_user(
            email=self.email.upper(),
            password="Passw0rd!",
            display_name="test",
            username=self.email.upper(),
            user_id="u" + uuid.uuid4().hex[:21],
        )
        self._set_captcha()
        resp = self._post_register()
        self.assertContains(resp, "already registered")

    def test_register_password_missing_digit(self):
        """
        Test that passwords without a digit are rejected.
        """
        self.pass1 = self.pass2 = "Password!"
        self._set_captcha()
        resp = self._post_register()
        self.assertContains(resp, "Password must be at least 8 characters")

    def test_register_password_missing_uppercase(self):
        """
        Test that passwords without an uppercase letter are rejected.
        """
        self.pass1 = self.pass2 = "password1"
        self._set_captcha()
        resp = self._post_register()
        self.assertContains(resp, "Password must be at least 8 characters")

    def test_register_password_missing_lowercase(self):
        """
        Test that passwords without a lowercase letter are rejected.
        """
        self.pass1 = self.pass2 = "PASSWORD1"
        self._set_captcha()
        resp = self._post_register()
        self.assertContains(resp, "Password must be at least 8 characters")

    def test_register_captcha_case_insensitive(self):
        """
        Test that the captcha input is case-insensitive.
        """
        self._set_captcha("ABCD")
        resp = self._post_register(captcha="abcd")
        self.assertRedirects(resp, self.url_verify)

    def test_verify_without_pending_email_redirects(self):
        """
        Test that accessing the verification page without a pending email
        redirects to the registration page.
        """
        resp = self.client.post(self.url_verify, {"code": "123456"})
        self.assertRedirects(resp, self.url_register)

    def test_verify_expired_cache_shows_error(self):
        """
        Test that verifying with an expired cache entry shows an error message.
        """
        self._set_captcha()
        self._post_register()
        cache.delete(f"pending_register:{self.email}")
        resp = self.client.post(self.url_verify, {"code": "123456"}, follow=True)
        self.assertContains(resp, "Verification expired")

    def test_resend_verification_without_pending_email(self):
        """
        Test that resending verification without a pending email
        redirects to the registration page.
        """
        self.client.logout()  # Ensure no user is logged in
        resp = self.client.get(self.url_resend)
        self.assertRedirects(resp, self.url_register)

    def test_resend_verification_cache_expired(self):
        """
        Test that resending verification after the cache entry has expired
        shows an error message.
        """
        self._set_captcha()
        self._post_register()
        cache.delete(f"pending_register:{self.email}")
        resp = self.client.get(self.url_resend, follow=True)
        self.assertContains(resp, "Verification expired")

    @override_settings(LOAD_TEST=True)
    def test_load_test_mode_auto_bypasses_verification(self):
        """
        With LOAD_TEST enabled:
        1. /register/ populates cache + session and redirects to /verify-email/
        2. First (and only) visit to /verify-email/ should immediately
           create the account, log the user in, delete the cache entry,
           and redirect to core:index.
        """
        # Step 1: submit registration *without following redirects*
        reg_resp = self.client.post(
            self.url_register,
            data={
                "email": self.email,
                "display_name": self.display,
                "password1": self.pass1,
                "password2": self.pass2,
                "captcha": "",          # captcha ignored in LOAD_TEST mode
            },
            follow=False,
        )
        self.assertEqual(reg_resp.status_code, 302)
        self.assertEqual(reg_resp["Location"], self.url_verify)

        # Step 2: first visit to /verify-email/
        verify_resp = self.client.get(self.url_verify, follow=False)
        self.assertEqual(verify_resp.status_code, 302)
        self.assertEqual(verify_resp["Location"], reverse("core:index"))

        # User was created and is now authenticated
        self.assertTrue(User.objects.filter(email=self.email).exists())
        self.assertIn("_auth_user_id", self.client.session)
