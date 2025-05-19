import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from business.models import Business
from review.models import Review

User = get_user_model()


class ReviewCreateDeleteTests(TestCase):
    def setUp(self):
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
            email="alice@gastronome.com",
            password="Passw0rd!",
            display_name="Alice",
            username="alice@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
            average_stars=4.0,
            review_count=5,
        )

        self.url_add = reverse("review:create_review", args=[self.biz.business_id])

    def _login(self):
        self.client.force_login(self.user)

    def test_create_review_updates_aggregates_incrementally(self):
        """After posting a review, both Business and User aggregates update via DB-side arithmetic."""
        self._login()
        self.client.post(self.url_add, {"stars": 5, "text": "Excellent!"})

        self.biz.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(self.biz.review_count, 11)
        self.assertAlmostEqual(self.biz.stars, ((4.2 * 10) + 5) / 11, places=3)
        self.assertEqual(self.user.review_count, 6)
        self.assertAlmostEqual(self.user.average_stars, ((4.0 * 5) + 5) / 6, places=3)

    def test_double_review_rejected(self):
        """Second attempt by same user should yield HTTP 400."""
        self._login()
        self.client.post(self.url_add, {"stars": 4, "text": "First"})
        resp = self.client.post(self.url_add, {"stars": 3, "text": "Again"})
        self.assertEqual(resp.status_code, 400)

    def test_anonymous_redirects_to_login(self):
        """GET by anonymous user triggers redirect to login."""
        resp = self.client.get(self.url_add)
        self.assertRedirects(resp, reverse("user:login"))

    def test_delete_review_restores_aggregates(self):
        """Deleting a review rolls aggregates back to original values."""
        self._login()
        self.client.post(self.url_add, {"stars": 5, "text": "Temp"})
        rev = Review.objects.get(business=self.biz, user=self.user)
        self.client.post(reverse("review:delete_review", args=[rev.review_id]))

        self.biz.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(self.biz.review_count, 10)
        self.assertAlmostEqual(self.biz.stars, 4.2, places=3)
        self.assertEqual(self.user.review_count, 5)
        self.assertAlmostEqual(self.user.average_stars, 4.0, places=3)

    def test_delete_last_review_sets_zero(self):
        """If a user deletes their only review, average_stars should reset to 0."""
        test = User.objects.create_user(
            email="test@gastronome.com",
            password="Passw0rd!",
            display_name="test",
            username="test@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
            average_stars=0.0,
            review_count=0,
        )
        self.client.force_login(test)
        self.client.post(self.url_add, {"stars": 5, "text": "Only one"})
        rev = Review.objects.get(business=self.biz, user=test)
        self.client.post(reverse("review:delete_review", args=[rev.review_id]))

        test.refresh_from_db()
        self.assertEqual(test.review_count, 0)
        self.assertEqual(test.average_stars, 0.0)
