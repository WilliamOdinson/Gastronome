import csv
import io
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from user.admin import (
    UserCreationForm,
    UserChangeForm,
    UserAdmin,
)

User = get_user_model()


class AdminFormTests(TestCase):
    def test_creation_form_password_mismatch_raises(self):
        """
        Test that UserCreationForm raises validation error
        when password1 and password2 do not match.
        """
        form = UserCreationForm(
            data={
                "email": "test@gastronome.com",
                "display_name": "test",
                "password1": "Passw0rd!",
                "password2": "Passw0rd!2",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Passwords don't match.", form.errors["password2"][0])

    def test_creation_form_saves_username_and_hash(self):
        """
        Test that UserCreationForm saves the username and hashes the password correctly.
        """
        form = UserCreationForm(
            data={
                "email": "test@gastronome.com",
                "display_name": "test",
                "password1": "Passw0rd!",
                "password2": "Passw0rd!",
            }
        )
        self.assertTrue(form.is_valid())
        user = form.save()  # commit=True default
        self.assertEqual(user.username, "test@gastronome.com")
        self.assertTrue(user.check_password("Passw0rd!"))

    def test_change_form_clean_password_returns_initial_hash(self):
        """
        Test that UserChangeForm's clean_password method returns the original hash
        when no new password is provided.
        """
        user = User.objects.create_user(
            email="test2@gastronome.com",
            display_name="test2",
            password="Passw0rd!",
            username="test2@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
        )
        form = UserChangeForm(instance=user, data={"email": user.email})
        # .clean_password() should echo the original hash from self.initial
        self.assertEqual(form.clean_password(), user.password)


class AdminActionTests(TestCase):
    """Exercise bulk actions defined on UserAdmin."""

    def setUp(self):
        self.factory = RequestFactory()
        self.admin_site = admin.site
        self.admin = UserAdmin(User, self.admin_site)

        self.u1 = User.objects.create_user(
            email="test3@gastronome.com",
            display_name="test3",
            password="Passw0rd!",
            username="test3@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
            is_active=False,
        )

        self.u2 = User.objects.create_user(
            email="test4@gastronome.com",
            display_name="test4",
            password="Passw0rd!",
            username="test4@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
            is_active=False,
            elite_years=[],
        )

        # Dummy request object with minimal attributes used by message_user()
        self.request = self.factory.post("/admin/")
        self.request.user = SimpleNamespace(is_staff=True, is_authenticated=True)
        # Patch ModelAdmin.message_user to no-op so we do not need messages framework
        self.admin.message_user = lambda *a, **kw: None

    def test_export_as_csv_response_content(self):
        """
        Test that export_as_csv returns a CSV response with correct headers and content.
        """
        response = self.admin.export_as_csv(self.request, User.objects.filter(pk=self.u1.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        # Parse CSV payload and verify header + first cell
        content = response.content.decode()
        reader = csv.reader(io.StringIO(content))
        header = next(reader)
        row = next(reader)
        self.assertIn("email", header)
        email_idx = header.index("email")
        self.assertEqual(row[email_idx], "test3@gastronome.com")

    def test_activate_users_sets_flag(self):
        """
        Test that activate_users sets is_active flag to True for selected users.
        """
        # First ensure both inactive
        User.objects.update(is_active=False)
        qs = User.objects.filter(pk__in=[self.u1.pk, self.u2.pk])
        self.admin.activate_users(self.request, qs)
        self.u1.refresh_from_db()
        self.u2.refresh_from_db()
        self.assertTrue(self.u1.is_active)
        self.assertTrue(self.u2.is_active)

    def test_deactivate_users_sets_flag(self):
        """
        Test that deactivate_users sets is_active flag to False for selected users.
        """
        # First ensure both active
        User.objects.update(is_active=True)
        qs = User.objects.filter(pk__in=[self.u1.pk, self.u2.pk])
        self.admin.deactivate_users(self.request, qs)
        self.u1.refresh_from_db()
        self.u2.refresh_from_db()
        self.assertFalse(self.u1.is_active)
        self.assertFalse(self.u2.is_active)

    def test_add_current_elite_adds_year_once(self):
        """
        Test that add_current_elite adds the current year to elite_years only once,
        even if the method is called multiple times.
        """
        self.u1.elite_years = []
        self.u1.save(update_fields=["elite_years"])
        self.u2.elite_years = []
        self.u2.save(update_fields=["elite_years"])
        year = date.today().year

        # Give u1 a past year to show additive behavior
        self.u1.elite_years = [year - 1]
        self.u1.save(update_fields=["elite_years"])

        qs = User.objects.filter(pk__in=[self.u1.pk, self.u2.pk])
        # First call
        self.admin.add_current_elite(self.request, qs)
        # Second call - should not re-add the same year
        self.admin.add_current_elite(self.request, qs)

        self.u1.refresh_from_db()
        self.u2.refresh_from_db()

        self.assertIn(year, self.u1.elite_years)
        self.assertIn(year, self.u2.elite_years)
        self.assertEqual(self.u1.elite_years.count(year), 1)
        self.assertEqual(self.u2.elite_years.count(year), 1)

    @patch("user.admin.send_verification_email.delay")
    def test_send_verification_again_sets_cache_and_dispatches_email(self, mock_delay):
        """
        Test that send_verification_again sets cache with verification code
        and dispatches email to the user.
        """
        qs = User.objects.filter(pk=self.u1.pk)
        self.admin.send_verification_again(self.request, qs)
        cache_key = f"pending_register:{self.u1.email}"
        cache_data = __import__("django.core.cache").core.cache.cache.get(cache_key)
        self.assertIsNotNone(cache_data)
        self.assertIn("verification_code", cache_data)
        mock_delay.assert_called_once_with(self.u1.email, cache_data["verification_code"])
