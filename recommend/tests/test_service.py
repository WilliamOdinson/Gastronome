import json
import types
import random
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


def _make_business(biz: str, stars: float = 4.5, reviews: int = 500, state: str = "PA") -> Business:
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
        services._MODELS.clear()
        cache.clear()

    def test_singleton_behavior(self):
        """_load_ensemble should load once and then reuse the model."""
        class DummyEnsemble:
            load_calls = 0

            @classmethod
            def load(cls, path):
                cls.load_calls += 1
                return f"<dummy-model:{path}>"

        fake_module = types.SimpleNamespace(EnsembleRecommender=DummyEnsemble)

        with mock.patch("recommend.services.import_module", return_value=fake_module):
            services._MODELS.clear()
            m1 = services._load_ensemble()
            m2 = services._load_ensemble()

        self.assertEqual(m1, m2)
        self.assertEqual(DummyEnsemble.load_calls, 1)


class GetUserRecommendationsTests(TestCase):
    def setUp(self):
        """get_user_recommendations should proxy predict() and return IDs only."""
        self.user = User.objects.create_user(
            username="user1",
            user_id="u1",
            display_name="User One",
            email="one@gastronome.com",
            password="x",
        )

    def tearDown(self):
        services._MODELS.clear()
        cache.clear()

    def test_returns_business_ids_from_model(self):
        """Returned list should contain only business_id values."""
        class FakeModel:
            def predict(self, uid, n=8):
                return [("b1", 9.9), ("b2", 9.5)]

        with mock.patch.object(services, "_load_ensemble", return_value=FakeModel()):
            ids = services.get_user_recommendations(self.user, state="PA", k=5)

        self.assertEqual(ids, ["b1", "b2"])


class GetStateHotlistTests(TestCase):
    def tearDown(self):
        cache.clear()

    @mock.patch("recommend.services.random.shuffle", lambda x: x)
    def test_only_high_rating_and_reviewcount(self):
        _good1 = _make_business("g1", stars=4.8, reviews=600, state="PA")
        _good2 = _make_business("g2", stars=4.2, reviews=450, state="PA")
        _make_business("b1", stars=3.5, reviews=800, state="PA")
        _make_business("b2", stars=4.7, reviews=100, state="PA")
        _make_business("b3", stars=4.9, reviews=700, state="NJ")

        ids = services.get_state_hotlist("PA", 3)
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
            password="Passw0rd!",
        )

        self._fake_task = types.SimpleNamespace(delay=lambda *a, **k: None)
        self._task_patcher = mock.patch("recommend.tasks.compute_user_recs", self._fake_task)
        self._task_patcher.start()

    def tearDown(self):
        self._task_patcher.stop()
        cache.clear()

    def _setup_user_reviews(self, n: int):
        """Create n reviews for self.user on biz_a."""
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
        """Eligible user but empty cache should trigger a hotlist fallback and async task."""
        self._setup_user_reviews(12)

        with mock.patch.object(services, "get_state_hotlist", return_value=["a1", "a2"]) as mock_hot:
            qs = services.fetch_recommendations(self.user, state="PA", n=8)
            self.assertQuerySetEqual(qs.order_by("business_id"),
                                     ["a1", "a2"],
                                     transform=lambda b: b.business_id)
            mock_hot.assert_called_once()

    def test_anonymous_user_uses_cached_state_hotlist(self):
        """Anonymous users rely solely on cached state hotlist."""
        anon = AnonymousUser()
        cache.set("rec:state:PA", '["a1"]', timeout=services.STATE_TIMEOUT)

        with mock.patch.object(services, "get_state_hotlist", side_effect=AssertionError("should not be called")):
            qs = services.fetch_recommendations(anon, state="PA", n=8)
            self.assertQuerySetEqual(qs, ["a1"], transform=lambda b: b.business_id)

    def test_user_with_few_reviews_falls_back_to_cached(self):
        """Logged-in user with <10 reviews also falls back to cached hotlist."""
        self._setup_user_reviews(2)
        cache.set("rec:state:PA", '["a2"]', timeout=services.STATE_TIMEOUT)

        with mock.patch.object(services, "get_state_hotlist", side_effect=AssertionError("should not be called")):
            qs = services.fetch_recommendations(self.user, state="PA", n=8)
            self.assertQuerySetEqual(qs, ["a2"], transform=lambda b: b.business_id)


class SampleKeepOrderTests(TestCase):
    def test_keeps_original_order(self):
        """Random sample must preserve original sequence order."""
        seq = list("ABCDEFGH")
        picked = services._sample_keep_order(seq, 5)
        self.assertTrue(all(ch in seq for ch in picked))
        self.assertEqual(sorted(seq.index(c) for c in picked), [seq.index(c) for c in picked])

    def test_len_smaller_than_k_returns_all(self):
        """When k exceeds length, return the whole list unchanged."""
        seq = ["x", "y"]
        self.assertEqual(services._sample_keep_order(seq, 5), seq)


class LoadEnsemblePerStateTests(TestCase):
    def tearDown(self):
        services._MODELS.clear()

    def test_two_states_use_two_slots(self):
        calls = {"n": 0}

        class Dummy:
            @classmethod
            def load(cls, _):
                calls["n"] += 1
                return f"<{calls['n']}>"

        with mock.patch("recommend.services.import_module", return_value=mock.Mock(EnsembleRecommender=Dummy)):
            services._load_ensemble("PA")
            services._load_ensemble("NJ")
            services._load_ensemble("PA")

        self.assertEqual(calls["n"], 2)


class SampleKeepOrderEdgeTests(TestCase):
    def test_k_equals_len(self):
        self.assertEqual(services._sample_keep_order(["a", "b", "c"], 3), ["a", "b", "c"])

    def test_k_zero(self):
        self.assertEqual(services._sample_keep_order(["x", "y"], 0), [])


class FetchRecommendationsCorruptedCacheTests(TestCase):
    def tearDown(self):
        cache.clear()

    def test_non_json_cache_fallback(self):
        """
        Broken JSON in state cache should be ignored; no hot-list recalculation
        for anonymous user; function just returns empty QS.
        """
        cache.set("rec:state:PA", "<<<not-json>>>", timeout=services.STATE_TIMEOUT)

        with mock.patch.object(services, "get_state_hotlist") as patched:
            qs = services.fetch_recommendations(mock.Mock(is_authenticated=False), state="PA", n=5)
            self.assertEqual(list(qs), [])
            patched.assert_not_called()


class GetStateHotlistUnderflowTests(TestCase):
    def tearDown(self):
        cache.clear()

    def test_returns_all_if_insufficient(self):
        Business.objects.all().delete()
        self.assertEqual(services.get_state_hotlist("PA", 10), [])
