import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from review.models import Tip

BATCH = 10_000


def parse_datetime(s: str):
    dt = (datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
          if " " in s
          else datetime.strptime(s, "%Y-%m-%d")
          )
    return timezone.make_aware(dt)


def stream(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


class Command(BaseCommand):
    help = "Imports tips from json file into the Tip model."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to yelp_academic_dataset_tip.json")

    @transaction.atomic
    def handle(self, *_, **opts):
        path = Path(opts["file"]).resolve()
        buf: List[Tip] = []

        for row in tqdm(stream(path), desc="Importing tips"):
            buf.append(
                Tip(
                    user_id=row["user_id"],
                    business_id=row["business_id"],
                    text=row["text"],
                    date=parse_datetime(row["date"]),
                    compliment_count=row["compliment_count"],
                )
            )

            if len(buf) >= BATCH:
                Tip.objects.bulk_create(buf, ignore_conflicts=True)
                buf.clear()

        if buf:
            Tip.objects.bulk_create(buf, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS("Tip import completed."))
