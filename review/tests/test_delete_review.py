"""
Unit‑tests focused on the  POST /review/delete/<review_id>/  endpoint.
They assume the incremental‑update logic implemented in review.views.delete_review.
"""
import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from business.models import Business
from review.models import Review

User = get_user_model()


class DeleteReviewTests(TestCase):
    def setUp(self):
        # Business record with aggregates coming from external source
        self.biz = Business.objects.create(
            business_id="biz_" + uuid.uuid4().hex[:18],   # ≤22 chars
            name="The Mock Café",
            address="1 Infinite Loop",
            city="Cupertino",
            state="CA",
            postal_code="95014",
            latitude=Decimal("37.3317"),
            longitude=Decimal("-122.0301"),
            stars=4.5,        # 2 historical reviews
            review_count=2,
            is_open=True,
        )

        # Author of the soon‑to‑be‑deleted review
        self.alice = User.objects.create_user(
            email="alice@test.com",
            password="Passw0rd!",
            display_name="Alice",
            username="alice@test.com",
            user_id="u" + uuid.uuid4().hex[:21],
            average_stars=4.5,   # aligned with biz (same two reviews)
            review_count=2,
        )

        # Another logged‑in user (not author)
        self.bob = User.objects.create_user(
            email="bob@test.com",
            password="Passw0rd!",
            display_name="Bob",
            username="bob@test.com",
            user_id="u" + uuid.uuid4().hex[:21],
        )

        # Concrete review row that belongs to Alice (only 1 of the 2 in aggregates)
        self.review = Review.objects.create(
            review_id="r" + uuid.uuid4().hex[:21],
            user=self.alice,
            business=self.biz,
            stars=5,
            text="Great!",
        )

        self.url_del = reverse("review:delete_review", args=[self.review.review_id])

    # utility
    def _login(self, user):
        self.client.force_login(user)

    # ─────────────────────────────────────────────── tests ──

    def test_author_can_delete_and_aggregates_update(self):
        """Alice deletes; business avg and counts updated with incremental formula."""
        self._login(self.alice)

        # Pre‑state
        b_old_cnt, b_old_avg = self.biz.review_count, self.biz.stars
        u_old_cnt, u_old_avg = self.alice.review_count, self.alice.average_stars

        response = self.client.post(self.url_del, follow=True)
        self.assertRedirects(response, reverse("user:profile"))

        self.biz.refresh_from_db(); self.alice.refresh_from_db()

        # biz: (4.5*2 - 5) / 1 = 4.0 ; count 1
        self.assertEqual(self.biz.review_count, b_old_cnt - 1)
        self.assertAlmostEqual(self.biz.stars,
                               ((b_old_avg * b_old_cnt) - 5) / (b_old_cnt - 1),
                               places=3)

        # alice: (4.5*2 - 5) / 1 = 4.0 ; count 1
        self.assertEqual(self.alice.review_count, u_old_cnt - 1)
        self.assertAlmostEqual(self.alice.average_stars,
                               ((u_old_avg * u_old_cnt) - 5) / (u_old_cnt - 1),
                               places=3)

        # db row gone
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())

    def test_get_method_not_allowed(self):
        self._login(self.alice)
        resp = self.client.get(self.url_del)
        self.assertEqual(resp.status_code, 405)

    def test_cannot_delete_someone_elses_review(self):
        self._login(self.bob)
        resp = self.client.post(self.url_del)
        self.assertEqual(resp.status_code, 404)

    def test_anonymous_redirects_to_login(self):
        resp = self.client.post(self.url_del, follow=False)
        login_base = reverse("user:login")
        
        expected   = f"{login_base}?next={self.url_del}"
        self.assertRedirects(resp, expected, fetch_redirect_response=False)
