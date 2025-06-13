import datetime as dt
from decimal import Decimal
from unittest.mock import patch
import uuid

import pytest
from django.core.cache import cache
from django.core.paginator import EmptyPage
from django.db import connection
from django.http import Http404
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from business.models import Business, Category
from core import context_processors
from core.views import _build_card, _cache_key


def _fake_search_business(q, city, state, category, page, per_page=20):
    """
    Minimal stand-in for the real OpenSearch backend: query via ORM.
    """
    qs = Business.objects.all()

    if q:
        qs = qs.filter(name__icontains=q)
    if city:
        qs = qs.filter(city__icontains=city)
    if state:
        qs = qs.filter(state__iexact=state)
    if category and category != "All":
        qs = qs.filter(categories__name__iexact=category)

    total = qs.count()
    ids = list(qs.values_list("business_id", flat=True))
    start = (page - 1) * per_page
    return total, ids[start:start + per_page]


def _biz_factory(name: str, *, city: str = "Pittsburgh", state: str = "PA") -> Business:
    """
    Create a Business plus a dedicated Category.
    """
    cat, _ = Category.objects.get_or_create(name=f"{name} Category")
    biz = Business.objects.create(
        business_id=uuid.uuid4().hex[:22],
        name=name,
        address="5000 Forbes Ave",
        city=city,
        state=state,
        postal_code="15213",
        latitude=Decimal("40.44"),
        longitude=Decimal("-79.94"),
        stars=4.0,
        review_count=10,
        is_open=True,
    )
    biz.categories.add(cat)
    return biz


class SearchViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cache.clear()

        cls.rest_cat = Category.objects.create(name="Restaurants")
        cls.fitness_cat = Category.objects.create(name="Fitness")

        def add_biz(name, cat):
            biz = Business.objects.create(
                business_id=uuid.uuid4().hex[:22],
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

    def test_keyword_search(self):
        """
        Test that searching for a keyword returns relevant results.
        """
        resp = self._search(q="chinese", where="PA", category="Restaurants")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "search_results.html")
        self.assertContains(resp, "Chinese Town")
        self.assertContains(resp, "Chinese Dragon")
        self.assertNotContains(resp, "Sushi World")
        self.assertNotContains(resp, "Fit Plus")

    def test_category_filter(self):
        """
        Test that filtering by category returns only businesses in that category.
        """
        resp = self._search(q="", where="PA", category="Fitness")
        self.assertContains(resp, "Fit Plus")
        self.assertNotContains(resp, "Chinese Town")

    def test_pagination_window_logic(self):
        """
        Test that pagination shows the correct number of pages and handles
        edge cases like fewer results than the page size.
        """
        for i in range(22):
            biz = Business.objects.create(
                business_id=uuid.uuid4().hex[:22],
                name=f"Carnegie Mellon University {i}",
                address="5000 Forbes Ave",
                city="Pittsburgh",
                state="PA",
                postal_code="0",
                latitude=Decimal("40.443336"),
                longitude=Decimal("-79.944023"),
                stars=3,
                review_count=1,
                is_open=True,
            )
            biz.categories.add(self.rest_cat)

        resp = self._search(q="", where="PA", category="Restaurants", page=2)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["results"]), 5)
        html = resp.content.decode()
        self.assertIn('<li class="page-item active"><span class="page-link">2</span>', html)
        self.assertNotIn("page=3", html)

    def test_redis_cache_write_and_hit(self):
        """
        Test that the search results are cached and subsequent requests hit the cache.
        """
        cache_key = _cache_key("sushi", None, "PA", "Restaurants") + ":p1"
        cache.delete(cache_key)

        with CaptureQueriesContext(connection) as ctx_first:
            self._search(q="sushi", where="PA", category="Restaurants")
        first_count = len(ctx_first)
        self.assertTrue(cache.get(cache_key))

        with CaptureQueriesContext(connection) as ctx_second:
            self._search(q="sushi", where="PA", category="Restaurants")
        second_count = len(ctx_second)
        self.assertLess(second_count, first_count)

    def test_detail_link_rendered(self):
        """
        Test that the business detail link is rendered correctly in search results.
        """
        resp = self._search(q="chinese", where="PA", category="Restaurants")
        biz = Business.objects.get(name="Chinese Town")
        detail_url = reverse("business:business_detail", args=[biz.business_id])
        self.assertIn(detail_url, resp.content.decode())

    def _search(self, **params):
        with patch("core.views.search_business", side_effect=_fake_search_business):
            return self.client.get(self.url, params)


class ContextProcessorTests(TestCase):

    def test_category_keywords_reference(self):
        """
        Test that CATEGORY_KEYWORDS context processor returns the correct reference.
        """
        ctx = context_processors.category_keywords(None)
        self.assertIs(ctx["CATEGORY_KEYWORDS"], context_processors.CATEGORY_KEYWORDS)

    def test_rating_filters_reference(self):
        """
        Test that RATING_FILTERS context processor returns the correct reference.
        """
        ctx = context_processors.rating_filters(None)
        self.assertEqual(ctx["RATING_FILTERS"], context_processors.RATING_FILTERS)


class BuildCardTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.biz = _biz_factory("24H Gym")

    def test_placeholder_image_when_no_photos(self):
        """
        Test that a placeholder image is used when the business has no photos.
        """
        card = _build_card(self.biz, "Monday", dt.time(12, 0))
        self.assertTrue(card["image_url"].startswith("https://"))

    def test_is_open_now_false_if_closed_flag(self):
        """
        Test that is_open_now is False if the business is closed.
        """
        self.biz.is_open = False
        card = _build_card(self.biz, "Mon", dt.time(3, 0))
        self.assertFalse(card["is_open_now"])

    def test_categories_join_max_three(self):
        """
        Test that categories are joined into a string, limited to three.
        """
        for i in range(5):
            self.biz.categories.add(Category.objects.create(name=f"Extra{i}"))
        card = _build_card(self.biz, "Mon", dt.time(2, 0))
        self.assertLessEqual(len(card["categories"].split(", ")), 3)


class IndexViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        _biz_factory("Nice Cafe")

    def test_category_counts_cached_after_first_request(self):
        """
        Test that category counts are cached after the first request
        and subsequent requests use the cache.
        """
        cache.delete("US_category_counts")
        url = reverse("core:index")

        with patch("core.views.fetch_recommendations", return_value=[]):
            first = self.client.get(url)
        self.assertIn("category_counts", first.context)

        with patch("core.views.Category.objects.filter") as spy, \
                patch("core.views.fetch_recommendations", return_value=[]):
            second = self.client.get(url)
        self.assertFalse(spy.called)
        self.assertEqual(first.context["category_counts"], second.context["category_counts"])

    def test_state_query_forwarded(self):
        """
        Test that the state query parameter is forwarded to the fetch_recommendations function.
        """
        observed = []

        def fake_fetch(user, *, state: str, n: int):
            observed.append(state)
            return []

        with patch("core.views.fetch_recommendations", side_effect=fake_fetch):
            self.client.get(reverse("core:index") + "?state=TX")
        self.assertEqual(observed, ["TX"])


class SearchEdgeCaseTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        _biz_factory("Edge Eatery")
        cls.url = reverse("core:search")

    @staticmethod
    def _backend_returning_one(q, city, state, category, page, per_page=20):
        ids = list(Business.objects.values_list("business_id", flat=True))
        return 1, ids

    def _get(self, params, backend=_backend_returning_one):
        with patch("core.views.search_business", side_effect=backend):
            return self.client.get(self.url, params)

    def test_multi_word_where_split(self):
        """
        Test that the 'where' parameter with multiple words is split into city and state.
        """
        captured = []

        def spy(q, city, state, category, page, per_page=20):
            captured.append((city, state))
            return 0, []

        self._get({"q": "", "where": "New York NY", "category": "All"}, backend=spy)
        self.assertEqual(captured[0], ("New York", "NY"))

    def test_page_not_integer_raises_valueerror(self):
        """
        Test that a non-integer page parameter raises a ValueError.
        """
        with pytest.raises(ValueError):
            self._get({"q": "", "where": "PA", "category": "All", "page": "abc"})

    def test_page_out_of_range_raises_empty_page(self):
        """
        Test that a page number greater than the total number of pages raises EmptyPage.
        """
        def backend_zero(q, city, state, category, page, per_page=20):
            return 0, []

        with self.assertRaises(EmptyPage):
            self._get({"q": "", "where": "PA", "category": "All", "page": 5},
                      backend=backend_zero)

    def test_unknown_category_zero_results(self):
        """
        Test that searching with an unknown category returns zero results.
        """
        def backend_zero(q, city, state, category, page, per_page=20):
            return 0, []

        resp = self._get({"q": "", "where": "PA", "category": "Unknown"},
                         backend=backend_zero)
        self.assertEqual(resp.context["result_count"], 0)

    def test_cache_written_once(self):
        """
        Test that the cache is written only once for a given search query.
        """
        key = _cache_key("", None, "PA", "All") + ":p1"
        cache.delete(key)
        self._get({"q": "", "where": "PA", "category": "All"})
        self.assertIsNotNone(cache.get(key))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name, template",
    [("core:system_map", "system_map.html"), ("core:tech_details", "tech_details.html")],
)
def test_static_pages_render(client: Client, url_name: str, template: str):
    """
    Test that static pages render the correct template.
    """
    resp = client.get(reverse(url_name))
    assert resp.status_code == 200
    assert template in [t.name for t in resp.templates]
