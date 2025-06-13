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
    """
    Behavioural tests for delete_review, including last-item edge cases.
    """

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
            stars=5.0,
            review_count=1,
            is_open=True,
        )

        self.alice = User.objects.create_user(
            email="alice@gastronome.com",
            password="Passw0rd!",
            display_name="Alice",
            username="alice@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
            average_stars=5.0,
            review_count=1,
        )

        self.review = Review.objects.create(
            review_id="r" + uuid.uuid4().hex[:21],
            user=self.alice,
            business=self.biz,
            stars=5,
            text="Great!",
        )
        self.url = reverse("review:delete_review", args=[self.review.pk])

    def _login(self, user):
        self.client.force_login(user)

    def test_author_can_delete_last_review_and_reset_aggregates(self):
        """
        Test that when the author delete their last review, resetting aggregates to zero.
        """
        self._login(self.alice)
        self.client.post(self.url)
        self.biz.refresh_from_db()
        self.alice.refresh_from_db()

        self.assertEqual(self.biz.review_count, 0)
        self.assertEqual(self.biz.stars, 0.0)
        self.assertEqual(self.alice.review_count, 0)
        self.assertEqual(self.alice.average_stars, 0.0)
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())

    def test_get_method_not_allowed(self):
        """
        Ensure GET requests to delete_review return 405.
        """
        self._login(self.alice)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_other_user_cannot_delete(self):
        """
        Test that another user cannot delete the review.
        """
        bob = User.objects.create_user(
            email="bob@gastronome.com",
            password="Passw0rd!",
            display_name="Bob",
            username="bob@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
        )
        self._login(bob)
        self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_anonymous_redirects_to_login(self):
        """
        Test that anonymous users are redirected to login when trying to delete a review.
        """
        resp = self.client.post(self.url, follow=False)
        login_url = f"{reverse('user:login')}?next={self.url}"
        self.assertRedirects(resp, login_url, fetch_redirect_response=False)
