import json
import re
from pathlib import Path
from typing import Iterable, List
from datetime import time

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.db import transaction

from business.models import Business, Category, Hour


BATCH = 5_000


def stream(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


def parse_time(value: str) -> time:
    """
    Parses a time string of the form 'H:M' or 'HH:MM' into a time object.
    """
    hour, minute = map(int, value.split(":"))
    return time(hour=hour, minute=minute)


class Command(BaseCommand):
    help = "Imports Business records, links existing Categories, and adds Hour entries from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to business.json")

    @transaction.atomic
    def handle(self, *_, **opts):
        f = Path(opts["file"]).resolve()
        cat_cache = {}
        batch = []
        hours_buffer = []

        for row in tqdm(stream(f), desc="Business"):
            b = Business(
                business_id=row["business_id"],
                name=row["name"],
                address=row["address"],
                city=row["city"],
                state=row["state"],
                postal_code=row["postal_code"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                stars=row["stars"],
                review_count=row["review_count"],
                is_open=row["is_open"] == 1,
                attributes=row.get("attributes") or None,
            )
            batch.append((b, row.get("categories"), row.get("hours")))

            if len(batch) >= BATCH:
                self._flush(batch, cat_cache, hours_buffer)
                batch.clear()

        if batch:
            self._flush(batch, cat_cache, hours_buffer)

        Hour.objects.bulk_create(hours_buffer, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS("Business import completed"))

    def _flush(self, data: List[tuple], cat_cache: dict, hours_acc: List[Hour]):
        businesses = [b for b, _, _ in data]
        Business.objects.bulk_create(businesses, ignore_conflicts=True)

        existing = {
            b.business_id: b for b in Business.objects.filter(
                business_id__in=[b.business_id for b in businesses]
            )
        }

        for b, cat_raw, hour_raw in data:
            instance = existing.get(b.business_id)
            if not instance:
                continue

            # Process categories
            if cat_raw:
                for name in re.split(r",\s*", cat_raw):
                    if name not in cat_cache:
                        try:
                            cat_cache[name] = Category.objects.get(name=name)
                        except Category.DoesNotExist:
                            continue
                    instance.categories.add(cat_cache[name])

            # Process hours
            if hour_raw:
                for day, time_range in hour_raw.items():
                    try:
                        open_str, close_str = time_range.split("-")
                        open_t = parse_time(open_str)
                        close_t = parse_time(close_str)
                        hours_acc.append(Hour(
                            business=instance,
                            day=day,
                            open_time=open_t,
                            close_time=close_t,
                        ))
                    except Exception:
                        continue
