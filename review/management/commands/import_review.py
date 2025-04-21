import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from review.models import Review

BATCH = 10_000


def parse_datetime(s: str):
    dt = datetime.strptime(
        s, "%Y-%m-%d %H:%M:%S") if " " in s else datetime.strptime(s, "%Y-%m-%d")
    return timezone.make_aware(dt)


def stream(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf‑8") as fh:
        for line in fh:
            yield json.loads(line)


class Command(BaseCommand):
    help = "Import review.json into the Review table"

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to review.json")

    @transaction.atomic
    def handle(self, *_, **opts):
        path = Path(opts["file"]).resolve()
        buf: List[Review] = []

        for row in tqdm(stream(path), desc="Review"):
            buf.append(
                Review(
                    review_id=row["review_id"],
                    user_id=row["user_id"],
                    business_id=row["business_id"],
                    stars=row["stars"],
                    date=parse_datetime(row["date"]),
                    text=row["text"],
                    useful=row["useful"],
                    funny=row["funny"],
                    cool=row["cool"],
                )
            )

            if len(buf) >= BATCH:
                Review.objects.bulk_create(buf, ignore_conflicts=True)
                buf.clear()

        if buf:
            Review.objects.bulk_create(buf, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS("Review import completed."))
