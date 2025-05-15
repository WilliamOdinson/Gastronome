from decimal import Decimal
import hashlib

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from business.models import Business, Category
from core.views import _make_cache_key


class SearchViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cache.clear()

        cls.rest_cat = Category.objects.create(name="Restaurants")
        cls.fitness_cat = Category.objects.create(name="Fitness")

        def add_biz(name, cat):
            biz = Business.objects.create(
                business_id=hashlib.md5(name.encode()).hexdigest()[:22],
                name=name,
                address="5000 Forbes Ave",
                city="Pittsburgh",
                state="PA",
                postal_code="15213",
                latitude=Decimal("40.443336"),
                longitude=Decimal("-79.944023"),
                stars=4.0,
                review_count=10,
                is_open=True,
            )
            biz.categories.add(cat)
            return biz

        add_biz("Chinese Town", cls.rest_cat)
        add_biz("Chinese Dragon", cls.rest_cat)
        add_biz("Sushi World", cls.rest_cat)
        add_biz("Fit Plus", cls.fitness_cat)

        cls.url = reverse("core:search")

    def _search(self, **params):
        return self.client.get(self.url, params)

    def test_keyword_search(self):
        """q='chinese' & category='Restaurants' returns the two Chinese restaurants only."""
        resp = self._search(q="chinese", where="PA", category="Restaurants")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "search_results.html")
        self.assertContains(resp, "Chinese Town")
        self.assertContains(resp, "Chinese Dragon")
        self.assertNotContains(resp, "Sushi World")
        self.assertNotContains(resp, "Fit Plus")

    def test_category_filter(self):
        """category='Fitness' returns only the gym."""
        resp = self._search(q="", where="PA", category="Fitness")
        self.assertContains(resp, "Fit Plus")
        self.assertNotContains(resp, "Chinese Town")

    def test_pagination_window_logic(self):
        """Add 22 extra restaurants (25 total). Page 2 shows 5 items, no page=3."""
        for i in range(22):
            biz = Business.objects.create(
                business_id=f"extra{i:02d}",
                name=f"Extra {i}",
                address="X", city="Pittsburgh", state="PA",
                postal_code="0", latitude=0, longitude=0,
                stars=3, review_count=1, is_open=True,
            )
            biz.categories.add(self.rest_cat)

        resp = self._search(q="", where="PA", category="Restaurants", page=2)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["results"]), 5)
        html = resp.content.decode()
        self.assertIn('<li class="page-item active"><span class="page-link">2</span>', html)
        self.assertNotIn('page=3', html)

    def test_redis_cache_write_and_hit(self):
        """First request stores in Redis, second uses cache with fewer DB queries."""
        cache_key = _make_cache_key("sushi", "PA", "Restaurants")
        cache.delete(cache_key)

        with CaptureQueriesContext(connection) as ctx_first:
            self._search(q="sushi", where="PA", category="Restaurants")
        first_count = len(ctx_first)
        self.assertTrue(cache.get(cache_key))

        with CaptureQueriesContext(connection) as ctx_second:
            self._search(q="sushi", where="PA", category="Restaurants")
        second_count = len(ctx_second)
        self.assertLess(second_count, first_count)
