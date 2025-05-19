import json
from pathlib import Path
from typing import Dict, List, Iterable

from django.core.management.base import BaseCommand
from django.db import transaction
from tqdm import tqdm

from review.models import Review

BATCH = 2_000


def stream(path: Path) -> Iterable[tuple[str, float]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            yield row["review_id"], float(row["predicted_stars"])


class Command(BaseCommand):
    help = "Import predicted_stars as auto_score into the Review table."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to review_predictions.json")

    @transaction.atomic
    def handle(self, *args, **opts):
        path = Path(opts["file"]).resolve()
        ids: List[str] = []
        scores: Dict[str, float] = {}
        updated = 0

        for review_id, score in tqdm(stream(path), desc="Importing auto_score"):
            ids.append(review_id)
            scores[review_id] = score

            if len(ids) >= BATCH:
                updated += self._bulk_update(ids, scores)
                ids.clear()
                scores.clear()

        if ids:
            updated += self._bulk_update(ids, scores)

        self.stdout.write(self.style.SUCCESS(f"Auto_score import completed."))

    def _bulk_update(self, ids: List[str], scores: Dict[str, float]) -> int:
        objs = list(Review.objects.filter(review_id__in=ids).only("review_id", "auto_score"))
        for obj in objs:
            obj.auto_score = scores[obj.review_id]
        Review.objects.bulk_update(objs, ["auto_score"])
        return len(objs)
