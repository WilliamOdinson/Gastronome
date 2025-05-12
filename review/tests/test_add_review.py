import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from business.models import Business
from review.models import Review

User = get_user_model()


class ReviewCreateDeleteTests(TestCase):
    def setUp(self):
        self.biz = Business.objects.create(
            business_id=uuid.uuid4().hex[:22],
            name="The Test Kitchen",
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
            email="alice@example.com",
            password="Passw0rd!",
            display_name="Alice",
            username="alice@example.com",
            user_id="u" + uuid.uuid4().hex[:21],
            average_stars=4.0,
            review_count=5,
        )

        self.url_add = reverse("review:create_review", args=[self.biz.business_id])

    def _login(self):
        self.client.force_login(self.user)

    def test_create_review_updates_aggregates_incrementally(self):
        self._login()
        self.client.post(self.url_add, {"stars": 5, "text": "Excellent!"})

        self.biz.refresh_from_db(); self.user.refresh_from_db()

        self.assertEqual(self.biz.review_count, 11)
        self.assertAlmostEqual(self.biz.stars, ((4.2 * 10) + 5) / 11, places=3)
        self.assertEqual(self.user.review_count, 6)
        self.assertAlmostEqual(self.user.average_stars, ((4.0 * 5) + 5) / 6, places=3)

    def test_double_review_rejected(self):
        self._login()
        self.client.post(self.url_add, {"stars": 4, "text": "First"})
        resp = self.client.post(self.url_add, {"stars": 3, "text": "Again"})
        self.assertEqual(resp.status_code, 400)

    def test_anonymous_redirects_to_login(self):
        resp = self.client.get(self.url_add)
        self.assertRedirects(resp, reverse("user:login"))

    def test_delete_review_restores_aggregates(self):
        self._login()
        self.client.post(self.url_add, {"stars": 5, "text": "Temp"})
        rev = Review.objects.get(business=self.biz, user=self.user)
        self.client.post(reverse("review:delete_review", args=[rev.review_id]))

        self.biz.refresh_from_db(); self.user.refresh_from_db()
        self.assertEqual(self.biz.review_count, 10)
        self.assertAlmostEqual(self.biz.stars, 4.2, places=3)
        self.assertEqual(self.user.review_count, 5)
        self.assertAlmostEqual(self.user.average_stars, 4.0, places=3)

    def test_delete_last_review_sets_zero(self):
        # user with no historical reviews
        solo = User.objects.create_user(
            email="solo@example.com",
            password="Passw0rd!",
            display_name="Solo",
            username="solo@example.com",
            user_id="u" + uuid.uuid4().hex[:21],
            average_stars=0.0,
            review_count=0,
        )
        self.client.force_login(solo)
        self.client.post(self.url_add, {"stars": 5, "text": "Only one"})
        rev = Review.objects.get(business=self.biz, user=solo)
        self.client.post(reverse("review:delete_review", args=[rev.review_id]))

        solo.refresh_from_db()
        self.assertEqual(solo.review_count, 0)
        self.assertEqual(solo.average_stars, 0.0)
