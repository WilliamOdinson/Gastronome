import uuid
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from business.models import Business
from review.models import Review

User = get_user_model()


class ReviewCreateDeleteTests(TestCase):
    def setUp(self):
        # Patch out the inference call so compute_auto_score.delay() will still be invoked
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
        """
        After posting a review, both Business and User aggregates update via DB-side arithmetic.
        """
        self._login()
        response = self.client.post(self.url_add, {"stars": 5, "text": "Excellent!"})
        self.assertEqual(response.status_code, 302)

        self.biz.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(self.biz.review_count, 11)
        self.assertAlmostEqual(self.biz.stars, ((4.2 * 10) + 5) / 11, places=3)
        self.assertEqual(self.user.review_count, 6)
        self.assertAlmostEqual(self.user.average_stars, ((4.0 * 5) + 5) / 6, places=3)

    def test_double_review_rejected(self):
        """
        Second attempt by same user to review immediately should yield HTTP 400,
        since the view checks for any review in the last 24 hours.
        """
        self._login()
        # First post is accepted
        resp1 = self.client.post(self.url_add, {"stars": 4, "text": "First"})
        self.assertEqual(resp1.status_code, 302)

        # Second post immediately after should be rejected (HTTP 400)
        resp2 = self.client.post(self.url_add, {"stars": 3, "text": "Again"})
        self.assertEqual(resp2.status_code, 400)

    def test_review_allowed_after_24_hours(self):
        """
        If the user's previous review for this business was more than 24 hours ago,
        a new review should be permitted.
        """
        self._login()

        # Manually create a "first" review timestamped 25 hours ago
        old_review = Review.objects.create(
            user=self.user,
            business=self.biz,
            review_id=uuid.uuid4().hex[:22],
            stars=4,
            text="Old review beyond 24h",
            date=timezone.now() - timedelta(hours=25),
        )
        response = self.client.post(self.url_add, {"stars": 5, "text": "New after 24h"})
        # Expect a redirect (302) to the business detail page
        self.assertEqual(response.status_code, 302)

        # There should now be two reviews for this user/business pair:
        reviews = Review.objects.filter(user=self.user, business=self.biz)
        self.assertEqual(reviews.count(), 2)

    def test_anonymous_redirects_to_login(self):
        """
        GET by anonymous user triggers redirect to login (HTTP 302).
        """
        resp = self.client.get(self.url_add)
        self.assertRedirects(resp, reverse("user:login"))

    def test_delete_review_restores_aggregates(self):
        """
        Deleting a review rolls aggregates back to original values.
        """
        self._login()

        # Create a new review first
        self.client.post(self.url_add, {"stars": 5, "text": "Temp"})
        rev = Review.objects.get(business=self.biz, user=self.user)

        # Delete it
        resp = self.client.post(reverse("review:delete_review", args=[rev.review_id]))
        self.assertEqual(resp.status_code, 302)

        self.biz.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(self.biz.review_count, 10)
        self.assertAlmostEqual(self.biz.stars, 4.2, places=3)
        self.assertEqual(self.user.review_count, 5)
        self.assertAlmostEqual(self.user.average_stars, 4.0, places=3)

    def test_delete_last_review_sets_zero(self):
        """
        If a user deletes their only review, average_stars should reset to 0.
        """
        test_user = User.objects.create_user(
            email="test@gastronome.com",
            password="Passw0rd!",
            display_name="test",
            username="test@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
            average_stars=0.0,
            review_count=0,
        )
        self.client.force_login(test_user)
        # Create the "only" review
        self.client.post(self.url_add, {"stars": 5, "text": "Only one"})
        rev = Review.objects.get(business=self.biz, user=test_user)

        # Delete it
        self.client.post(reverse("review:delete_review", args=[rev.review_id]))
        test_user.refresh_from_db()
        self.assertEqual(test_user.review_count, 0)
        self.assertEqual(test_user.average_stars, 0.0)

    def test_hourly_limit_distinct_businesses(self):
        """
        A user may post up to three reviews for different businesses within one hour.
        The fourth review for a different business within the same hour should be rejected (HTTP 400).
        """
        self._login()

        # Create three additional businesses
        biz2 = Business.objects.create(
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
        biz3 = Business.objects.create(
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
        biz4 = Business.objects.create(
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

        # 1st review on self.biz
        resp1 = self.client.post(
            reverse("review:create_review", args=[self.biz.business_id]),
            {"stars": 5, "text": "Carnegie Mellon University"},
        )
        self.assertEqual(resp1.status_code, 302)

        # 2nd review on biz2
        resp2 = self.client.post(
            reverse("review:create_review", args=[biz2.business_id]),
            {"stars": 4, "text": "Carnegie Mellon University"},
        )
        self.assertEqual(resp2.status_code, 302)

        # 3rd review on biz3
        resp3 = self.client.post(
            reverse("review:create_review", args=[biz3.business_id]),
            {"stars": 3, "text": "Carnegie Mellon University"},
        )
        self.assertEqual(resp3.status_code, 302)

        # 4th review on biz4 within the same hour should be rejected
        resp4 = self.client.post(
            reverse("review:create_review", args=[biz4.business_id]),
            {"stars": 2, "text": "Review 4 on biz4"},
        )
        self.assertEqual(resp4.status_code, 400)
        self.assertIn(b"more than three reviews for different businesses", resp4.content)

    def test_deletion_resets_hourly_quota(self):
        """
        After posting three reviews for distinct businesses within an hour, deleting one should allow
        a new review on a different business (count falls below limit).
        """
        self._login()

        biz2 = Business.objects.create(
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
        biz3 = Business.objects.create(
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
        biz4 = Business.objects.create(
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

        # Post three reviews on distinct businesses
        self.client.post(
            reverse("review:create_review", args=[self.biz.business_id]),
            {"stars": 5, "text": "Carnegie Mellon University"},
        )
        self.client.post(
            reverse("review:create_review", args=[biz2.business_id]),
            {"stars": 4, "text": "Carnegie Mellon University"},
        )
        self.client.post(
            reverse("review:create_review", args=[biz3.business_id]),
            {"stars": 3, "text": "Carnegie Mellon University"},
        )

        # Verify that the three reviews exist
        reviews = Review.objects.filter(user=self.user)
        self.assertEqual(reviews.count(), 3)

        # Delete the review on biz2
        rev_to_delete = Review.objects.get(user=self.user, business=biz2)
        del_resp = self.client.post(
            reverse("review:delete_review", args=[rev_to_delete.review_id])
        )
        self.assertEqual(del_resp.status_code, 302)

        # Now only two reviews remain in the past hour
        remaining_count = Review.objects.filter(
            user=self.user, date__gte=timezone.now() - timedelta(hours=1)
        ).count()
        self.assertEqual(remaining_count, 2)

        # Posting a new review on biz4 should now be allowed (this becomes the third)
        new_resp = self.client.post(
            reverse("review:create_review", args=[biz4.business_id]),
            {"stars": 5, "text": "New after deletion"},
        )
        self.assertEqual(new_resp.status_code, 302)

        # Confirm the total in-past-hour count is back to three
        after_count = Review.objects.filter(
            user=self.user, date__gte=timezone.now() - timedelta(hours=1)
        ).count()
        self.assertEqual(after_count, 3)


class ReviewAsyncTaskTests(TransactionTestCase):
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
        self.client.force_login(self.user)

    def test_auto_score_task_enqueued_on_commit(self):
        """
        After creating a comment, the asynchronous auto-score task
        should be queued upon transaction submission.
        """
        with patch("review.views.compute_auto_score.delay") as mock_delay:
            self.client.post(self.url_add, {"stars": 5, "text": "Asynchronous!"})

            rev = Review.objects.get(business=self.biz, user=self.user)
            mock_delay.assert_called_once_with(rev.pk)
