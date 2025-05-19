import types
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from business.models import Business
from review.models import Review
from recommend import services

User = get_user_model()


def _make_business(biz: str, stars=4.5, reviews=500, state="PA") -> Business:
    return Business.objects.create(
        business_id=biz,
        name=f"Carnegie Mellon University {biz}",
        address="5000 Forbes Ave",
        city="Pittsburgh",
        state=state,
        postal_code="15213",
        latitude=Decimal("40.443336"),
        longitude=Decimal("-79.944023"),
        stars=stars,
        review_count=reviews,
        is_open=True,
    )


class LoadEnsembleTests(TestCase):
    def tearDown(self):
        services._MODEL = None
        cache.clear()

    def test_singleton_behavior(self):
        class DummyEnsemble:
            load_calls = 0

            @classmethod
            def load(cls, path):
                cls.load_calls += 1
                return f"<dummy-model:{path}>"

        fake_module = types.SimpleNamespace(EnsembleRecommender=DummyEnsemble)

        with mock.patch("recommend.services.import_module", return_value=fake_module):
            services._MODEL = None
            m1 = services._load_ensemble()
            m2 = services._load_ensemble()

        self.assertEqual(m1, m2)
        self.assertEqual(DummyEnsemble.load_calls, 1)


class GetUserRecommendationsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user1",
            user_id="u1",
            display_name="User One",
            email="a@gastronome.com",
            password="x",
        )

    def tearDown(self):
        services._MODEL = None
        cache.clear()

    def test_returns_business_ids_from_model(self):
        class FakeModel:
            def __init__(self):
                self.calls = []

            def predict(self, uid, n=8):
                self.calls.append((uid, n))
                return [("b1", 9.9), ("b2", 9.5)]

        with mock.patch.object(services, "_load_ensemble", return_value=FakeModel()):
            ids = services.get_user_recommendations(self.user, n=5)

        self.assertEqual(ids, ["b1", "b2"])


class GetStateHotlistTests(TestCase):
    def tearDown(self):
        cache.clear()

    @mock.patch("recommend.services.random.shuffle", lambda x: x)
    def test_only_high_rating_and_reviewcount(self):
        good1 = _make_business("g1", stars=4.8, reviews=600, state="PA")
        good2 = _make_business("g2", stars=4.2, reviews=450, state="PA")
        _make_business("b1", stars=3.5, reviews=800, state="PA")
        _make_business("b2", stars=4.7, reviews=100, state="PA")
        _make_business("b3", stars=4.9, reviews=700, state="NJ")

        ids = services.get_state_hotlist("PA", n=3)
        self.assertTrue(all(bid in {"g1", "g2"} for bid in ids))
        self.assertEqual(len(ids), 2)


class FetchRecommendationsTests(TestCase):
    def setUp(self):
        cache.clear()
        self._review_counter = 0
        self.biz_a = _make_business("a1")
        self.biz_b = _make_business("a2")
        self.user = User.objects.create_user(
            username="user2",
            user_id="u2",
            display_name="User Two",
            email="u2@gastronome.com",
            password="x",
        )

    def tearDown(self):
        cache.clear()

    def _setup_user_reviews(self, n: int):
        for _ in range(n):
            self._review_counter += 1
            Review.objects.create(
                review_id=f"rvw-{self.user.pk}-{self.biz_a.pk}-{self._review_counter}",
                user=self.user,
                business=self.biz_a,
                stars=5,
                date=timezone.now(),
                text="Great!",
            )

    def test_authenticated_user_with_enough_reviews(self):
        self._setup_user_reviews(12)
        with mock.patch.object(
            services, "get_user_recommendations", return_value=["a1", "a2"]
        ) as mock_user_rec:
            qs = services.fetch_recommendations(self.user, state="PA", n=8)
            self.assertQuerySetEqual(
                qs.order_by("business_id"),
                ["a1", "a2"],
                transform=lambda b: b.business_id)
            mock_user_rec.assert_called_once()

        with mock.patch.object(
            services, "get_user_recommendations", side_effect=AssertionError("Should hit cache")
        ):
            _ = services.fetch_recommendations(self.user, state="PA", n=8)

    def test_anonymous_user_uses_state_hotlist(self):
        anon = AnonymousUser()
        with mock.patch.object(
            services, "get_state_hotlist", return_value=["a1"]
        ) as mock_hot:
            qs = services.fetch_recommendations(anon, state="PA", n=8)
            self.assertQuerySetEqual(qs, ["a1"], transform=lambda b: b.business_id)
            mock_hot.assert_called_once()

    def test_user_with_few_reviews_falls_back(self):
        self._setup_user_reviews(2)
        with mock.patch.object(
            services, "get_state_hotlist", return_value=["a2"]
        ) as mock_hot:
            qs = services.fetch_recommendations(self.user, state="PA", n=8)
            self.assertQuerySetEqual(qs, ["a2"], transform=lambda b: b.business_id)
            mock_hot.assert_called_once()
