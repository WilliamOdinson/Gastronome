from pathlib import Path
from typing import Iterable, Set
import json

from django.core.management.base import BaseCommand
from business.models import Category
from tqdm import tqdm


def stream(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf‑8") as fh:
        for line in fh:
            yield json.loads(line)


class Command(BaseCommand):
    help = "Import unique categories from business.json → Category"

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to yelp_academic_dataset_business.json")

    def handle(self, *_, **opts):
        path = Path(opts["file"]).resolve()
        if not path.exists():
            self.stderr.write(f"File not found: {path}")
            return

        seen: Set[str] = set(Category.objects.values_list("name", flat=True))  # existing in DB
        new_cats = set()

        for row in tqdm(stream(path), desc="Scanning categories"):
            raw = row.get("categories")
            if raw:
                for name in map(str.strip, raw.split(",")):
                    if name and name not in seen:
                        new_cats.add(name)
                        seen.add(name)

        # Bulk create new categories
        Category.objects.bulk_create(
            [Category(name=cat) for cat in new_cats],
            ignore_conflicts=True
        )

        self.stdout.write(self.style.SUCCESS(f"Inserted {len(new_cats)} new categories"))
