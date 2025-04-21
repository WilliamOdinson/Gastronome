import json
from pathlib import Path
from typing import Iterable, List

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.db import transaction

from business.models import Business, Category, Hour


BATCH = 500


def stream(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf‑8") as fh:
        for line in fh:
            yield json.loads(line)


class Command(BaseCommand):
    help = "Imports business records from json file into the Business, Category and Hour model."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to business.json")

    @transaction.atomic
    def handle(self, *_, **opts):
        f = Path(opts["file"]).resolve()
        cat_cache, hours, batch = {}, [], []

        for row in tqdm(stream(f), desc="Business"):
            batch.append(
                Business(
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
            )
            
            if len(batch) >= BATCH:
                self._flush(batch, row, cat_cache, hours)
                batch.clear()

        if batch:
            self._flush(batch, row, cat_cache, hours)

        Hour.objects.bulk_create(hours, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS("Business import completed"))

    def _flush(self, records: List[Business], sample, cache, hours_acc):
        Business.objects.bulk_create(records, ignore_conflicts=True)
        for b in records:
            for c in (sample["categories"] or []):
                if c not in cache:
                    cache[c], _ = Category.objects.get_or_create(name=c)
                b.categories.add(cache[c])
            for d, span in (sample.get("hours") or {}).items():
                o, c = span.split("-")
                hours_acc.append(
                    Hour(business=b, day=d, open_time=o, close_time=c))
