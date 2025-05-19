import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from review.models import Review
from user.models import User

BATCH = 5_000


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
    help = "Imports reviews from json file into the Review model."

    def add_arguments(self, parser):
        parser.add_argument(
            "file", help="Path to yelp_academic_dataset_review.json")

    @transaction.atomic
    def handle(self, *_, **opts):
        file_path = Path(opts["file"]).resolve()
        buf: List[Review] = []
        existing_user_ids = set(User.objects.values_list("user_id", flat=True))
        for row in tqdm(stream(file_path), desc="Importing reviews"):
            if row["user_id"] not in existing_user_ids:
                continue
            buf.append(
                Review(
                    review_id=row["review_id"],
                    user_id=row["user_id"],
                    business_id=row["business_id"],
                    stars=row["stars"],
                    date=parse_datetime(row["date"]),
                    text=row["text"],
                    useful=max(0, row["useful"]),
                    funny=max(0, row["funny"]),
                    cool=max(0, row["cool"]),
                )
            )

            if len(buf) >= BATCH:
                Review.objects.bulk_create(buf, ignore_conflicts=True)
                buf.clear()

        if buf:
            Review.objects.bulk_create(buf, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS("Review import completed."))
