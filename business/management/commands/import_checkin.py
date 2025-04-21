import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from business.models import Business, CheckIn


BATCH = 5_000


def stream(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf‑8") as fh:
        for line in fh:
            yield json.loads(line)


class Command(BaseCommand):
    help = "Imports check-in records from json file into the CheckIn model."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to checkin.json")

    @transaction.atomic
    def handle(self, *_, **opts):
        f = Path(opts["file"]).resolve()
        buf: List[CheckIn] = []

        for row in tqdm(stream(f), desc="Check-ins"):
            bid = row["business_id"]
            for dt_str in row["date"].split(", "):
                
                dt = timezone.make_aware(datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S"))
                buf.append(CheckIn(business_id=bid, checkin_time=dt))

            if len(buf) >= BATCH:
                CheckIn.objects.bulk_create(buf, ignore_conflicts=True)
                buf.clear()

        if buf:
            CheckIn.objects.bulk_create(buf, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS("Check-in import completed"))
