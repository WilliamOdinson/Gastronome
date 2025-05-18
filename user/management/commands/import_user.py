from datetime import datetime
from django.utils import timezone
from pathlib import Path
from typing import Iterable, List
import json

from django.core.management.base import BaseCommand
from django.db import transaction
from tqdm import tqdm

from user.models import User

BATCH = 5_000
PROGRESS = {"users": 0}


def parse_datetime(s: str):
    dt = datetime.strptime(
        s, "%Y-%m-%d %H:%M:%S") if " " in s else datetime.strptime(s, "%Y-%m-%d")
    return timezone.make_aware(dt)


def stream(path: Path) -> Iterable[dict]:
    """Yield one dict per line from Yelp JSON‑lines file."""
    with path.open(encoding="utf‑8") as fh:
        for line in fh:
            yield json.loads(line)


def bulk_insert(model, objects: List, label: str):
    """General batch insert and clear buffer."""
    if objects:
        model.objects.bulk_create(objects, ignore_conflicts=True)
        PROGRESS[label] += len(objects)
        objects.clear()


class Command(BaseCommand):
    help = "Imports user account from json file into the User model."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to user.json")

    def handle(self, *_, **opts):
        path = Path(opts["file"]).resolve()
        if not path.exists():
            self.stderr.write(f"File not found: {path}")
            return

        self._load_users(path)

    @transaction.atomic
    def _load_users(self, path: Path):
        buf: List[User] = []

        for row in tqdm(stream(path), desc="User pass"):
            raw_friends = row.get("friends", "")
            friends_list = [fid.strip() for fid in raw_friends.split(",")] if raw_friends else []
            buf.append(
                User(
                    user_id=row["user_id"],
                    username=row["user_id"],
                    display_name=row["name"] or row["user_id"],
                    yelping_since=parse_datetime(row["yelping_since"]),
                    review_count=row["review_count"],
                    useful=row["useful"],
                    funny=row["funny"],
                    cool=row["cool"],
                    fans=row["fans"],
                    average_stars=row["average_stars"],
                    elite_years=row.get("elite", []),
                    compliment_hot=row["compliment_hot"],
                    compliment_more=row["compliment_more"],
                    compliment_profile=row["compliment_profile"],
                    compliment_cute=row["compliment_cute"],
                    compliment_list=row["compliment_list"],
                    compliment_note=row["compliment_note"],
                    compliment_plain=row["compliment_plain"],
                    compliment_cool=row["compliment_cool"],
                    compliment_funny=row["compliment_funny"],
                    compliment_writer=row["compliment_writer"],
                    compliment_photos=row["compliment_photos"],
                    friends=friends_list,
                )
            )

            if len(buf) >= BATCH:
                bulk_insert(User, buf, "users")

        bulk_insert(User, buf, "users")
        self.stdout.write(self.style.SUCCESS("User import completed"))
