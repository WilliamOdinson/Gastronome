import json
import uuid
from decimal import Decimal
from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.urls import reverse

from business.models import Business
from recommend import admin as rec_admin
from recommend.admin import BusinessStateAdmin, PersonalRecAdmin, TOP_K
from recommend.tasks import compute_user_recs, precache_recommendations
from user.models import User


def _biz(state: str, stars=4.5, reviews=500):
    return Business.objects.create(
        business_id=f"biz-{uuid.uuid4().hex[:8]}",
        name="Carnegie Mellon University",
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


def _req(user):
    req = RequestFactory().post("/")
    req.user = user
    req.session = {}
    req._messages = FallbackStorage(req)
    return req


class _MemRedis(dict):
    def scan_iter(self, pattern):
        for k in list(self):
            if k.startswith("rec:user:"):
                yield k

    def delete(self, key):
        return super().pop(key, None) is not None


class AdminActionTests(TestCase):
    def setUp(self):
        self.super = User.objects.create_superuser(
            email="root@g.com", password="x", username="root",
            user_id="u" + uuid.uuid4().hex[:21],
        )
        site = AdminSite()
        self.p_admin = PersonalRecAdmin(User, site)
        self.s_admin = BusinessStateAdmin(rec_admin.BusinessState, site)
        self.req = _req(self.super)
        cache.clear()

    def test_compute_personal_recs_queues_for_each(self):
        """
        Test that compute_personal_recs queues a task for each user in the queryset.
        """
        u1 = User.objects.create_user(
            email="user1@gastronome.com",
            password="Passw0rd!",
            display_name="user1",
            username="user1@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
        )
        u2 = User.objects.create_user(
            email="user2@gastronome.com",
            password="Passw0rd!",
            display_name="user2",
            username="user2@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
        )

        calls = []

        def fake_delay(*args, **kw):
            calls.append((args, kw))

        with mock.patch.object(compute_user_recs, "delay", side_effect=fake_delay):
            qs = User.objects.filter(pk__in=[u1.pk, u2.pk])
            self.p_admin.compute_personal_recs(self.req, qs)

        self.assertEqual(len(calls), 2)
        self.assertTrue(all(kw["state"] == "PA" for _, kw in calls))

    def test_flush_personal_cache(self):
        """
        Test that flushing personal cache deletes the cache key for each user.
        """
        test = User.objects.create_user(
            email="test@gastronome.com",
            password="Passw0rd!",
            display_name="test",
            username="test@gastronome.com",
            user_id="u" + uuid.uuid4().hex[:21],
        )
        cache.set(f"rec:user:{test.pk}", "dummy")
        self.p_admin.flush_personal_cache(self.req, User.objects.filter(pk=test.pk))
        self.assertIsNone(cache.get(f"rec:user:{test.pk}"))

    def _state_qs(self, code):
        from recommend.admin import BusinessState
        return BusinessState.objects.filter(state=code)

    def test_state_changelist_rows(self):
        """
        Test that the state changelist shows correct rows and totals.
        """
        for _ in range(3):
            _biz("PA")
        for _ in range(2):
            _biz("CA")

        cl_request = _req(self.super)
        cl_request.path = reverse("admin:recommend_businessstate_changelist")

        cl = self.s_admin.get_changelist_instance(cl_request)
        cl.get_results(cl_request)

        states = {row.state for row in cl.result_list}
        self.assertEqual(states, {"PA", "CA"})
        pa = next(r for r in cl.result_list if r.state == "PA")
        self.assertEqual(pa._total_reviews, 3 * 500)

    def test_get_state_hotlist_action_sets_cache(self):
        """
        Test that get_state_hotlist_action fetches the hotlist and caches it.
        """
        _biz("PA")
        with mock.patch.object(rec_admin, "get_state_hotlist", return_value=["X"]) as gh:
            self.s_admin.get_state_hotlist_action(self.req, self._state_qs("PA"))
            gh.assert_called_once_with("PA", TOP_K)
        self.assertEqual(json.loads(cache.get("rec:state:PA")), ["X"])

    def test_flush_state_hotlist_cache_deletes_key(self):
        """
        Test that flushing the state hotlist cache deletes the cache key for the state.
        """
        _biz("PA")
        cache.set("rec:state:PA", "foo")
        self.s_admin.flush_state_hotlist_cache(self.req, self._state_qs("PA"))
        self.assertIsNone(cache.get("rec:state:PA"))

    def test_run_precache_recommendations_only_if_PA(self):
        """
        Test that run_precache_recommendations only queues a task for PA state.
        """
        _biz("CA")
        with mock.patch.object(precache_recommendations, "delay") as delay:
            self.s_admin.run_precache_recommendations(self.req, self._state_qs("CA"))
            delay.assert_not_called()

            _biz("PA")
            self.s_admin.run_precache_recommendations(self.req, self._state_qs("PA"))
            delay.assert_called_once()

    def test_flush_precache_cache_behaviour(self):
        """
        Test that flushing the precache cache deletes the state key and all user keys.
        """
        _biz("PA")
        cache.set("rec:state:PA", "zzz")
        cache.set("rec:user:42", "abc")

        fake_redis = _MemRedis()
        fake_redis["rec:user:42"] = "abc"

        with mock.patch.object(rec_admin, "get_redis_connection", return_value=fake_redis):
            # without PA - no deletion
            self.s_admin.flush_precache_cache(self.req, self._state_qs("CA"))
            self.assertIsNotNone(cache.get("rec:state:PA"))

            # with PA - everything flushed
            self.s_admin.flush_precache_cache(self.req, self._state_qs("PA"))
            self.assertIsNone(cache.get("rec:state:PA"))
            self.assertNotIn("rec:user:42", fake_redis)
