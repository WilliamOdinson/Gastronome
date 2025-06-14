import uuid
from decimal import Decimal
from zoneinfo import ZoneInfo
from unittest.mock import patch

from django.test import TestCase, SimpleTestCase

from business.models import Business
from business.views import parse_amenities


class BusinessTimezoneTests(TestCase):
    """Business.get_timezone should infer a zone and persist it."""

    @patch("business.models.TimezoneFinder.timezone_at", return_value="America/Chicago")
    def test_infer_and_persist_timezone(self, mock_tz_at):
        """
        Test that Business.get_timezone infers a timezone and persists it.
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
            stars=5.0,
            review_count=1,
            is_open=True,
            timezone=None,
        )
        zone = biz.get_timezone()
        self.assertEqual(zone, ZoneInfo("America/Chicago"))
        biz.refresh_from_db()
        self.assertEqual(biz.timezone, "America/Chicago")


class ParseAmenitiesTests(SimpleTestCase):
    """parse_amenities must flatten, filter and coerce raw attributes."""

    def test_nested_and_boolean_values(self):
        """
        Test that parse_amenities flattens nested dictionaries and filters
        out None and empty values.
        """
        raw = {
            "WiFi": "u'free'",
            "BikeParking": "True",
            "Parking": "{'garage': False, 'street': True}",
            "Alcohol": "None",
            "OutdoorSeating": False,
        }
        result = parse_amenities(raw)
        self.assertIn("WiFi: u'free'", result)
        self.assertIn("BikeParking", result)
        self.assertIn("Parking.street", result)
        self.assertNotIn("Parking.garage", result)
