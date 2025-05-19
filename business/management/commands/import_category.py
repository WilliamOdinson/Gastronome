import json
from pathlib import Path
from typing import Iterable, Set

from django.core.management.base import BaseCommand
from django.db import transaction

from business.models import Category
from tqdm import tqdm


def stream(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


class Command(BaseCommand):
    help = "Imports unique categories from json file into the Category model."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to yelp_academic_dataset_business.json")

    @transaction.atomic
    def handle(self, *_, **opts):
        file_path = Path(opts["file"]).resolve()
        seen: Set[str] = set(Category.objects.values_list("name", flat=True))
        new_cats = set()

        for row in tqdm(stream(file_path), desc="Scanning unique categories"):
            raw = row.get("categories")
            if raw:
                for name in map(str.strip, raw.split(",")):
                    if name and name not in seen:
                        new_cats.add(name)
                        seen.add(name)

        Category.objects.bulk_create(
            [Category(name=cat) for cat in new_cats],
            ignore_conflicts=True
        )

        self.stdout.write(self.style.SUCCESS(f"Inserted {len(new_cats)} new categories"))
