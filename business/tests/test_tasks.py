import uuid
from datetime import datetime, time
from decimal import Decimal
from typing import List
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from business.models import Business, Hour
from business.tasks import _batched, refresh_open_batch, refresh_open_status


def _make_business(
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
        business_id=uuid.uuid4().hex[:22],
        name=f"Carnegie Mellon University",
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
    """
    Edge-case coverage for Business.calculate_open_status.
    """

    def test_within_hours(self):
        """
        Test that calculate_open_status returns True when the current time
        is within the business's open hours.
        """
        now = _aware(datetime(2025, 1, 6, 12))
        biz = _make_business(weekday="Monday", open_t=time(9), close_t=time(17))
        self.assertTrue(biz.calculate_open_status(now))

    def test_outside_hours(self):
        """
        Test that calculate_open_status returns False when the current time
        is outside the business's open hours.
        """
        now = _aware(datetime(2025, 1, 6, 22))
        biz = _make_business(weekday="Monday", open_t=time(9), close_t=time(17), is_open=True)
        self.assertFalse(biz.calculate_open_status(now))

    def test_open_boundary_inclusive(self):
        """
        Test that calculate_open_status returns True at the exact opening time.
        """
        for hour in (9, 17):
            now = _aware(datetime(2025, 1, 6, hour))
            biz = _make_business(weekday="Monday", open_t=time(9), close_t=time(17))
            self.assertTrue(biz.calculate_open_status(now))

    def test_cross_midnight(self):
        """
        Test that calculate_open_status correctly handles businesses that
        close after midnight.
        """
        before_midnight = _aware(datetime(2025, 1, 6, 23, 30))
        after_midnight = _aware(datetime(2025, 1, 7, 1, 30))
        biz = _make_business(weekday="Monday", open_t=time(18), close_t=time(2))
        self.assertTrue(biz.calculate_open_status(before_midnight))
        self.assertFalse(biz.calculate_open_status(after_midnight))

    def test_24_hours_variants(self):
        """
        Test that calculate_open_status handles 24-hour open businesses correctly.
        """
        for open_t, close_t in ((0, 0), (10, 10)):
            now = _aware(datetime(2025, 1, 8, 3))
            biz = _make_business(weekday="Wednesday", open_t=time(open_t), close_t=time(close_t),)
            self.assertTrue(biz.calculate_open_status(now))

    def test_no_hours_returns_closed(self):
        """
        Test that calculate_open_status returns False when no hours are defined.
        """
        biz = Business.objects.create(
            business_id=uuid.uuid4().hex[:22],
            name="Carnegie Mellon University",
            address="5000 Forbes Ave",
            city="Pittsburgh",
            state="PA",
            postal_code="15213",
            latitude=Decimal("40.443336"),
            longitude=Decimal("-79.944023"),
            stars=5,
            review_count=1,
            is_open=True,
            timezone="UTC",
        )
        self.assertFalse(biz.calculate_open_status(timezone.now()))


class CeleryTaskTests(TestCase):
    """Run tasks synchronously; no broker or OpenSearch needed."""

    @patch("business.tasks.push_is_open_bulk.delay")
    @patch("business.tasks.timezone.now")
    def test_refresh_open_batch_updates_flag(self, mock_now, mock_delay):
        """
        Test that refresh_open_batch updates the is_open flag and calls the push task.
        """
        mock_now.return_value = _aware(datetime(2025, 1, 9, 10))
        biz = _make_business(weekday="Thursday", open_t=time(9), close_t=time(17), is_open=False)

        changed = refresh_open_batch([biz.business_id])
        biz.refresh_from_db()

        self.assertEqual(changed, 1)
        self.assertTrue(biz.is_open)
        mock_delay.assert_called_once_with([biz.business_id])

    @patch("business.tasks.push_is_open_bulk.delay")
    @patch("business.tasks.timezone.now")
    def test_refresh_open_batch_no_change(self, mock_now, mock_delay):
        """
        Test that refresh_open_batch does not update the is_open flag if no change occurs.
        """
        mock_now.return_value = _aware(datetime(2025, 1, 10, 3))
        biz = _make_business(weekday="Friday", open_t=time(0), close_t=time(0), is_open=True)
        changed = refresh_open_batch([biz.business_id])
        self.assertEqual(changed, 0)
        mock_delay.assert_not_called()

    @patch("business.tasks.group")
    def test_refresh_open_status_dispatch(self, mock_group):
        """
        Test that refresh_open_status dispatches tasks for all businesses.
        """
        _make_business(weekday="Monday", open_t=time(9), close_t=time(17))

        captured: List = []

        def fake_group(sigs):
            captured.extend(sigs)

            class _Dummy:
                id = "dummy"

                def apply_async(self, queue=None):
                    return self

            return _Dummy()

        mock_group.side_effect = fake_group
        refresh_open_status()

        self.assertGreater(len(captured), 0)
        for sig in captured:
            self.assertEqual(sig.options.get("queue"), "business_status")

    def test_batched_helper(self):
        """
        _batched must return full, ordered partitions of the source iterable.
        """
        data = list("abcdefghij")
        expected = [["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"], ["j"]]
        self.assertEqual(list(_batched(data, 3)), expected)
