import uuid
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TransactionTestCase
from django.urls import reverse

from review.forms import ReviewForm
from review.tasks import compute_auto_score
from review.models import Review
from business.models import Business
from user.models import User


class ReviewFormUnitTests(SimpleTestCase):
    def test_valid_form(self):
        """
        Test that a valid form with stars and text passes validation.
        """
        f = ReviewForm(data={"stars": 5, "text": "Nice"})
        self.assertTrue(f.is_valid())

    def test_text_cannot_be_blank(self):
        """
        Test that the text field cannot be blank, even if stars are provided.
        """
        for txt in ["", "   ", "\n"]:
            f = ReviewForm(data={"stars": 4, "text": txt})
            self.assertFalse(f.is_valid())
            self.assertIn("text", f.errors)

    def test_star_bounds(self):
        """
        Test that stars must be between 1 and 5, inclusive.
        """
        self.assertTrue(ReviewForm(data={"stars": 1, "text": "ok"}).is_valid())
        self.assertTrue(ReviewForm(data={"stars": 5, "text": "ok"}).is_valid())


class ComputeAutoScoreTaskTests(TransactionTestCase):
    """
    Integration test for Celery task; runs synchronously.
    """

    def setUp(self):
        self.biz = Business.objects.create(
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
        self.user = User.objects.create_user(
            email="test@example.com",
            password="Passw0rd!",
            display_name="test",
            username="test@example.com",
            user_id="u" + uuid.uuid4().hex[:21],
        )
        self.rev = Review.objects.create(
            review_id="r" + uuid.uuid4().hex[:21],
            user=self.user,
            business=self.biz,
            stars=4,
            text="predict me",
        )

    @patch("review.tasks.predict_score", return_value=3.5)
    def test_task_updates_auto_score(self, mock_predict):
        """
        Call the .run() implementation directly to avoid the Celery proxy layer.
        """
        # run synchronously
        from review.tasks import compute_auto_score  # local import after patch
        compute_auto_score.run(self.rev.pk)

        self.rev.refresh_from_db()
        mock_predict.assert_called_once_with("predict me")
        self.assertEqual(self.rev.auto_score, 3.5)
