import json
import re
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
        parser.add_argument("file", help="Path to business.json")

    @transaction.atomic
    def handle(self, *_, **opts):
        f = Path(opts["file"]).resolve()
        cat_cache = {}
        batch = []
        m2m = []

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
            batch.append((b, row.get("categories")))

            if len(batch) >= BATCH:
                self._flush(batch, cat_cache)
                batch.clear()

        if batch:
            self._flush(batch, cat_cache)

        self.stdout.write(self.style.SUCCESS("Business import completed"))

    def _flush(self, data: List[tuple], cat_cache):
        businesses = [b for b, _ in data]
        Business.objects.bulk_create(businesses, ignore_conflicts=True)

        existing = {
            b.business_id: b for b in Business.objects.filter(
                business_id__in=[b.business_id for b in businesses]
            )
        }

        for b, raw in data:
            instance = existing.get(b.business_id)
            if not instance or not raw:
                continue
            for name in re.split(r",\s*", raw):
                if name not in cat_cache:
                    try:
                        cat_cache[name] = Category.objects.get(name=name)
                    except Category.DoesNotExist:
                        continue
                instance.categories.add(cat_cache[name])
