import json
from pathlib import Path
from typing import Iterable, List

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.db import transaction

from business.models import Photo


BATCH = 10_000


def stream(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


class Command(BaseCommand):
    help = "Imports photo records from json file into the photo model."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to photo.json")

    @transaction.atomic
    def handle(self, *_, **opts):
        path = Path(opts["file"]).resolve()
        buf: List[Photo] = []

        for row in tqdm(stream(path), desc="Photo"):
            buf.append(
                Photo(
                    photo_id=row["photo_id"],
                    business_id=row["business_id"],
                    caption=row.get("caption") or None,
                    label=row.get("label") or None,
                )
            )

            if len(buf) >= BATCH:
                Photo.objects.bulk_create(buf, ignore_conflicts=True)
                buf.clear()

        if buf:
            Photo.objects.bulk_create(buf, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS("Photo import completed."))
