import csv
import io
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from business.models import Business
from review.models import Review

User = get_user_model()

opensearch = {"REVIEW_INDEX": "django_test_review", "TIP_INDEX": "django_test_tip"}


def _fake_search_factory(expected_ids, capture):
    """
    Return a stub op.search callable that records the DSL body and spits
    back hits containing the provided IDs (preserving order).
    """

    def _fake_search(*, body, index, **kw):
        # record for later inspection
        capture["body"] = body
        capture["index"] = index
        return {
            "hits": {
                "total": {"value": len(expected_ids)},
                "hits": [{"_id": rid} for rid in expected_ids],
            }
        }

    return _fake_search


@override_settings(OPENSEARCH=opensearch)
class AdminReviewTests(TestCase):
    def setUp(self):
        # Create staff user for admin login
        self.admin = User.objects.create_superuser(
            email="staff@gastronome.com",
            password="Passw0rd!",
            user_id="u" + uuid.uuid4().hex[:21],
        )

        # Create a business + three reviews so ORM hydration can succeed
        self.biz = Business.objects.create(
            business_id=uuid.uuid4().hex[:22],
            name="Carnegie Mellon University",
            address="5000 Forbes",
            city="Pittsburgh",
            state="PA",
            postal_code="15213",
            latitude=Decimal("40.443336"),
            longitude=Decimal("-79.944023"),
            stars=4.0,
            review_count=3,
            is_open=True,
        )

        self.reviews = [
            Review.objects.create(
                review_id="r" + uuid.uuid4().hex[:21],
                user=self.admin,  # re-using same user
                business=self.biz,
                stars=5,
                text=f"review #{i}",
            )
            for i in range(3)
        ]

        # Changelist URL
        self.cl_url = reverse("admin:review_review_changelist")
        self.client.force_login(self.admin)

    def test_changelist_builds_correct_dsl(self):
        """
        Test that the admin changelist builds the correct OpenSearch DSL for the given query parameters.
        """
        capture: dict[str, object] = {}
        with patch("review.admin.op.search",
                   new=_fake_search_factory([r.pk for r in self.reviews], capture)):
            # '?q=great&stars__exact=5&auto_score=low&o=2.1' :
            #   o=2.1 means ascending order on column #2 -> 'stars'
            resp = self.client.get(
                self.cl_url,
                {
                    "q": "great",
                    "stars__exact": "5",
                    "auto_score": "low",
                    "o": "2"  # column index for 'stars' asc in Django admin
                },
            )
            self.assertEqual(resp.status_code, 200)

        body = capture["body"]
        # Search term => multi_match bool_prefix field
        mutli_match = body["query"]["bool"]["must"][0]["multi_match"]
        self.assertEqual(mutli_match["query"], "great")
        self.assertIn("user_name.ng", mutli_match["fields"])

        # stars exact => term filter
        star_filter = [flt for flt in body["query"]["bool"]["filter"] if "term" in flt][0]
        self.assertEqual(star_filter["term"]["stars"], 5)

        # auto_score low bucket => range lt 2.0
        rng = [flt for flt in body["query"]["bool"]["filter"] if "range" in flt][0]
        self.assertEqual(rng["range"]["auto_score"]["lt"], 2.0)

        # sort clause asc on stars
        sort_clause = body["sort"][0]
        self.assertEqual(sort_clause["stars"]["order"], "asc")

        # index selection
        self.assertEqual(capture["index"], opensearch["REVIEW_INDEX"])

    def test_export_csv_action(self):
        """
        Test that the export action generates a CSV file with the selected reviews' data.
        """
        selected = [self.reviews[0].pk, self.reviews[1].pk]
        with patch("review.admin.op.search",
                   new=_fake_search_factory([*selected], {})):
            resp = self.client.post(
                self.cl_url,
                {
                    "action": "export",
                    "_selected_action": selected,
                },
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        # Parse CSV and ensure two lines of data (plus header)
        content = resp.content.decode()
        rows = list(csv.reader(io.StringIO(content)))
        self.assertEqual(len(rows) - 1, 2)  # header + 2 data rows

    def test_recompute_auto_score_action(self):
        """
        Test that recompute_auto_score action calls compute_auto_score.delay
        with the selected review IDs.
        """
        rid = self.reviews[0].pk
        called = {}

        def fake_delay(x):
            called.setdefault("ids", []).append(x)

        with patch("review.admin.compute_auto_score.delay", side_effect=fake_delay):
            with patch("review.admin.op.search",
                       new=_fake_search_factory([rid], {})):
                self.client.post(
                    self.cl_url,
                    {
                        "action": "recompute_auto_score",
                        "_selected_action": [rid],
                    },
                    follow=True,
                )
        self.assertEqual(called["ids"], [rid])

    def _test_increment_action(self, action_name, field_name):
        before = getattr(self.reviews[0], field_name)
        with patch("review.admin.op.search",
                   new=_fake_search_factory([self.reviews[0].pk], {})):
            self.client.post(
                self.cl_url,
                {
                    "action": action_name,
                    "_selected_action": [self.reviews[0].pk],
                },
                follow=True,
            )
        self.reviews[0].refresh_from_db()
        self.assertEqual(getattr(self.reviews[0], field_name), before + 1)

    def test_add_useful(self):
        """
        Test that add_useful action increments the 'useful' field of selected reviews.
        """
        self._test_increment_action("add_useful", "useful")

    def test_add_funny(self):
        """
        Test that add_funny action increments the 'funny' field of selected reviews.
        """
        self._test_increment_action("add_funny", "funny")

    def test_add_cool(self):
        """
        Test that add_cool action increments the 'cool' field of selected reviews.
        """
        self._test_increment_action("add_cool", "cool")
