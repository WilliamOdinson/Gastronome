import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable, List

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.db import transaction

from business.models import Business, Category


BATCH = 1_000


def stream(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


class Command(BaseCommand):
    help = "Imports business records from json file into the Business model and links to existing Category records."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to yelp_academic_dataset_business.json")

    @transaction.atomic
    def handle(self, *_, **opts):
        file_path = Path(opts["file"]).resolve()
        cat_cache: dict[str, Category] = {}
        batch: List[tuple[Business, str | None]] = []

        for row in tqdm(stream(file_path), desc="Importing businesses"):
            lat = Decimal(str(row["latitude"])).quantize(
                Decimal("0.000001"), ROUND_HALF_UP
            )
            lon = Decimal(str(row["longitude"])).quantize(
                Decimal("0.000001"), ROUND_HALF_UP
            )

            raw_attr = row.get("attributes")
            attributes = raw_attr if isinstance(raw_attr, dict) else None

            business = Business(
                business_id=row["business_id"],
                name=row["name"],
                address=row["address"],
                city=row["city"],
                state=row["state"],
                postal_code=row["postal_code"],
                latitude=lat,
                longitude=lon,
                stars=row["stars"],
                review_count=row["review_count"],
                is_open=row["is_open"] == 1,
                attributes=attributes,
            )
            batch.append((business, row.get("categories")))

            if len(batch) >= BATCH:
                self._flush(batch, cat_cache)
                batch.clear()

        if batch:
            self._flush(batch, cat_cache)

        self.stdout.write(self.style.SUCCESS("Business import completed"))

    def _flush(self, data: List[tuple], cat_cache: dict[str, Category]):
        """
        Bulk-insert the current slice of Business rows, then attach
        many-to-many Category links with the help of an in-memory cache.
        """
        businesses = [b for b, _ in data]
        Business.objects.bulk_create(businesses, ignore_conflicts=True)

        existing = {
            b.business_id: b
            for b in Business.objects.filter(
                business_id__in=[b.business_id for b in businesses]
            )
        }

        for biz, raw_cats in data:
            instance = existing.get(biz.business_id)
            if not instance or not raw_cats:
                continue

            for name in re.split(r",\s*", raw_cats):
                if not name:
                    continue
                if name not in cat_cache:
                    try:
                        cat_cache[name] = Category.objects.get(name=name)
                    except Category.DoesNotExist:
                        continue
                instance.categories.add(cat_cache[name])
