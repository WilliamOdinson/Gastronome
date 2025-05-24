from decimal import Decimal
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import List
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from business.models import Business, Hour
from business.tasks import refresh_open_batch, refresh_open_status


def _make_business(
    biz_id: str,
    *,
    weekday: str,
    open_t: time,
    close_t: time,
    stars: float = 4.5,
    reviews: int = 500,
    state: str = "PA",
    tz_name: str = "America/New_York",
    is_open: bool = False,
) -> Business:
    """Create a Business and one Hour row."""
    biz = Business.objects.create(
        business_id=biz_id,
        name=f"Carnegie Mellon University {biz_id}",
        address="5000 Forbes Ave",
        city="Pittsburgh",
        state=state,
        postal_code="15213",
        latitude=Decimal("40.443336"),
        longitude=Decimal("-79.944023"),
        stars=stars,
        review_count=reviews,
        is_open=is_open,
        timezone=tz_name,
    )
    Hour.objects.create(
        business=biz,
        day=weekday,
        open_time=open_t,
        close_time=close_t,
    )
    return biz


def _aware(dt: datetime, tz: str = "America/New_York") -> datetime:
    return dt.replace(tzinfo=ZoneInfo(tz))


class BusinessOpenStatusTests(TestCase):
    """Edge-case coverage for Business.calculate_open_status."""

    def test_within_hours(self):
        now = _aware(datetime(2025, 1, 6, 12, 0))
        biz = _make_business(
            "within",
            weekday="Monday",
            open_t=time(9, 0),
            close_t=time(17, 0),
        )
        self.assertTrue(biz.calculate_open_status(now))

    def test_outside_hours(self):
        now = _aware(datetime(2025, 1, 6, 22, 0))
        biz = _make_business(
            "outside",
            weekday="Monday",
            open_t=time(9, 0),
            close_t=time(17, 0),
            is_open=True,
        )
        self.assertFalse(biz.calculate_open_status(now))

    def test_cross_midnight_before(self):
        now = _aware(datetime(2025, 1, 6, 23, 30))
        biz = _make_business(
            "cross_before",
            weekday="Monday",
            open_t=time(18, 0),
            close_t=time(2, 0),
        )
        self.assertTrue(biz.calculate_open_status(now))

    def test_cross_midnight_after(self):
        now = _aware(datetime(2025, 1, 7, 1, 30))
        biz = _make_business(
            "cross_after",
            weekday="Monday",
            open_t=time(18, 0),
            close_t=time(2, 0),
        )
        self.assertFalse(biz.calculate_open_status(now))

    def test_open_24_hours(self):
        now = _aware(datetime(2025, 1, 8, 3, 0))
        biz = _make_business(
            "all_day",
            weekday="Wednesday",
            open_t=time(0, 0),
            close_t=time(0, 0),
        )
        self.assertTrue(biz.calculate_open_status(now))

    def test_no_hours_returns_closed(self):
        biz = Business.objects.create(
            business_id="no_hours",
            name="No Hours",
            address="x",
            city="Pittsburgh",
            state="PA",
            postal_code="00000",
            latitude=Decimal("0"),
            longitude=Decimal("0"),
            stars=5,
            review_count=1,
            is_open=True,
            timezone="UTC",
        )
        self.assertFalse(biz.calculate_open_status(timezone.now()))


class CeleryTaskTests(TestCase):
    """Run tasks synchronously; no broker or worker needed."""

    @patch("business.tasks.timezone.now")
    def test_refresh_open_batch_updates_flag(self, mock_now):
        now = _aware(datetime(2025, 1, 9, 10, 0))
        mock_now.return_value = now
        biz = _make_business(
            "batch",
            weekday="Thursday",
            open_t=time(9, 0),
            close_t=time(17, 0),
            is_open=False,
        )

        changed = refresh_open_batch([biz.business_id])
        biz.refresh_from_db()

        self.assertEqual(changed, 1)
        self.assertTrue(biz.is_open)

    @patch("business.tasks.group")
    def test_refresh_open_status_dispatch(self, mock_group):
        # ensure at least one Business so batches are generated
        _make_business(
            "dummy",
            weekday="Monday",
            open_t=time(9, 0),
            close_t=time(17, 0),
        )

        collected: List = []

        def fake_group(signatures):
            collected.extend(signatures)

            class DummyRes:
                id = "dummy"

                def apply_async(self, queue=None):
                    return self
            return DummyRes()

        mock_group.side_effect = fake_group
        refresh_open_status()

        self.assertGreater(len(collected), 0)
        for sig in collected:
            self.assertEqual(sig.options.get("queue"), "business_status")
