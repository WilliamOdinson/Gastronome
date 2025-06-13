import uuid
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from business.models import Business
from review.models import Review

User = get_user_model()


class ReviewCreateTests(TestCase):
    """
    End-to-end tests for create_review view, including all guard-rails.
    """

    def setUp(self):
        # Stub out BERT inference everywhere in this module
        patcher = patch("api.inference.predict_score", return_value=4)
        self.addCleanup(patcher.stop)
        patcher.start()

        self.biz = Business.objects.create(
            business_id=uuid.uuid4().hex[:22],
            name="Carnegie Mellon University",
            address="5000 Forbes Ave",
            city="Pittsburgh",
            state="PA",
            postal_code="15213",
            latitude=Decimal("40.443336"),
            longitude=Decimal("-79.944023"),
            stars=4.2,
            review_count=10,
            is_open=True,
        )
        self.user = User.objects.create_user(
            email="test@gastronome.com",
            password="Passw0rd!",
            display_name="test",
            username="test@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
            average_stars=4.0,
            review_count=5,
        )
        self.url = reverse("review:create_review", args=[self.biz.pk])

    def _login(self):
        self.client.force_login(self.user)

    def test_create_review_updates_aggregates(self):
        """
        Test that creating a review updates the business and user aggregates correctly.
        """
        self._login()
        self.client.post(self.url, {"stars": 5, "text": "Excellent!"})

        self.biz.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(self.biz.review_count, 11)
        self.assertAlmostEqual(self.biz.stars, ((4.2 * 10) + 5) / 11, places=3)
        self.assertEqual(self.user.review_count, 6)
        self.assertAlmostEqual(self.user.average_stars, ((4.0 * 5) + 5) / 6, places=3)

    def test_double_review_same_business_blocked_within_24h(self):
        """
        Test that a user cannot review the same business more than once within 24 hours.
        """
        self._login()
        self.client.post(self.url, {"stars": 4, "text": "First review"})
        resp = self.client.post(self.url, {"stars": 3, "text": "Second review"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"already reviewed this business", resp.content)

    def test_hourly_quota_three_distinct_businesses(self):
        """
        Test that a user can only review 3 distinct businesses per hour.
        """
        self._login()
        for _ in range(2):
            Business.objects.create(
                business_id=uuid.uuid4().hex[:22],
                name=f"Carnegie Mellon University{_}",
                address="5000 Forbes Ave",
                city="Pittsburgh",
                state="PA",
                postal_code="15213",
                latitude=Decimal("40.443336"),
                longitude=Decimal("-79.944023"),
                stars=4,
                review_count=0,
                is_open=True,
            )
        biz_ids = list(Business.objects.values_list("pk", flat=True))[:3]

        # Posting three reviews is OK
        for biz_id in biz_ids:
            resp = self.client.post(
                reverse("review:create_review", args=[biz_id]),
                {"stars": 4, "text": "test"},
            )
            self.assertEqual(resp.status_code, 302)

        # Fourth distinct business triggers 400
        biz4 = Business.objects.create(
            business_id=uuid.uuid4().hex[:22],
            name="Carnegie Mellon University",
            address="5000 Forbes Ave",
            city="Pittsburgh",
            state="PA",
            postal_code="15213",
            latitude=Decimal("40.443336"),
            longitude=Decimal("-79.944023"),
            stars=4,
            review_count=0,
            is_open=True,
        )

        resp4 = self.client.post(
            reverse("review:create_review", args=[biz4.pk]),
            {"stars": 4, "text": "test"},
        )
        self.assertEqual(resp4.status_code, 400)

    @override_settings(LOAD_TEST=True)
    def test_hourly_limit_disabled_when_load_test_true(self):
        """
        In load test mode, the hourly limit of 3 distinct businesses is disabled.
        """
        self._login()
        biz_list = [
            Business.objects.create(
                business_id=uuid.uuid4().hex[:22],
                name=f"Carnegie Mellon University{i}",
                address="5000 Forbes Ave",
                city="Pittsburgh",
                state="PA",
                postal_code="15213",
                latitude=Decimal("40.443336"),
                longitude=Decimal("-79.944023"),
                stars=4,
                review_count=0,
                is_open=True,
            )
            for i in range(4)
        ]
        for biz in biz_list:
            r = self.client.post(
                reverse("review:create_review", args=[biz.pk]),
                {"stars": 4, "text": "bulk"},
            )
            self.assertEqual(r.status_code, 302)

    def test_get_authenticated_renders_form(self):
        """
        Test that authenticated users see the review form.
        """
        self._login()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "create_review.html")

    def test_post_invalid_form_returns_200_with_errors(self):
        """
        Test that posting an invalid form returns 200 and shows errors.
        """
        self._login()
        resp = self.client.post(self.url, {"stars": 5, "text": ""})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "This field is required.")

    def test_anonymous_redirects_to_login(self):
        """
        Test that anonymous users are redirected to the login page.
        """
        resp = self.client.get(self.url)
        self.assertRedirects(resp, reverse("user:login"))

    def test_missing_business_returns_404(self):
        """
        Test that trying to review a non-existent business returns 404.
        """
        self._login()
        bad = reverse("review:create_review", args=["nonexistent"])
        self.assertEqual(self.client.get(bad).status_code, 404)

    def test_review_allowed_after_24h(self):
        """
        Test that a user can review the same business again after 24 hours.
        """
        self._login()
        old = Review.objects.create(
            review_id=uuid.uuid4().hex[:22],
            user=self.user,
            business=self.biz,
            stars=3,
            text="old",
            date=timezone.now() - timedelta(hours=25),
        )
        resp = self.client.post(self.url, {"stars": 5, "text": "new"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            Review.objects.filter(user=self.user, business=self.biz).count(), 2
        )
