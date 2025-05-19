import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from business.models import Business
from review.models import Review


User = get_user_model()


class DeleteReviewTests(TestCase):
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
            stars=4.5,
            review_count=2,
            is_open=True,
        )

        self.alice = User.objects.create_user(
            email="alice@gastronome.com",
            password="Passw0rd!",
            display_name="Alice",
            username="alice@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
            average_stars=4.5,
            review_count=2,
        )

        self.bob = User.objects.create_user(
            email="bob@gastronome.com",
            password="Passw0rd!",
            display_name="Bob",
            username="bob@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
        )

        self.review = Review.objects.create(
            review_id="r" + uuid.uuid4().hex[:21],
            user=self.alice,
            business=self.biz,
            stars=5,
            text="Great!",
        )

        self.url_del = reverse("review:delete_review", args=[self.review.review_id])

    def _login(self, user):
        self.client.force_login(user)

    def test_author_can_delete_and_aggregates_update(self):
        self._login(self.alice)

        b_old_cnt, b_old_avg = self.biz.review_count, self.biz.stars
        u_old_cnt, u_old_avg = self.alice.review_count, self.alice.average_stars

        response = self.client.post(self.url_del, follow=True)
        self.assertRedirects(response, reverse("user:profile"))

        self.biz.refresh_from_db()
        self.alice.refresh_from_db()

        self.assertEqual(self.biz.review_count, b_old_cnt - 1)
        self.assertAlmostEqual(
            self.biz.stars,
            ((b_old_avg * b_old_cnt) - 5) / (b_old_cnt - 1),
            places=3,
        )

        self.assertEqual(self.alice.review_count, u_old_cnt - 1)
        self.assertAlmostEqual(
            self.alice.average_stars,
            ((u_old_avg * u_old_cnt) - 5) / (u_old_cnt - 1),
            places=3,
        )

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
        expected = f"{login_base}?next={self.url_del}"
        self.assertRedirects(resp, expected, fetch_redirect_response=False)
