from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand

from recommend.algorithm.svd_recommender import SVDRecommender


class Command(BaseCommand):
    """
    Train and save a bias-corrected truncated SVD model for a single state.
    """

    help = "Train and save SVD model for a given state (default: PA)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--state",
            type=str,
            default="PA",
            help="Target US state two-letter code (e.g. PA, CA)",
        )

    def handle(self, *args, **options):
        state = options["state"].upper()
        state_lower = state.lower()

        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        csv_path = base_dir / "database" / "Yelp_final.csv"
        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
            return

        model_dir = base_dir / "assets" / "weights" / "svd"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / f"svd_{state_lower}.pkl"

        self.stdout.write(f"Loading data from {csv_path}")
        df = pd.read_csv(csv_path)
        df = df[df.state == state]

        self.stdout.write(f"Training SVD model for state {state}")
        model = SVDRecommender(
            k=10,
            state=state,
            min_user_review=10,
        )
        model.fit(df)
        model.save(model_path)
        self.stdout.write(
            self.style.SUCCESS(f"SVD model for {state} saved successfully.")
        )
