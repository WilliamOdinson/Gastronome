from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand

from recommend.algorithm.sgd_recommender import SGDRecommender


class Command(BaseCommand):
    """
    Train and save an SGD matrix-factorisation model for a single US state.
    """

    help = "Train and save SGD model for a given state (default: PA)"

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

        model_dir = base_dir / "assets" / "weights" / "sgd"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / f"sgd_{state_lower}.pkl"

        self.stdout.write(f"Loading data from {csv_path}")
        df = pd.read_csv(csv_path)
        df = df[df.state == state]

        self.stdout.write(f"Training SGD model for state {state}")
        model = SGDRecommender(
            k=40,
            iterations=200,
            state=state,
            min_user_review=10,
            learning_rate=1e-3,
            user_bias_reg=0.01,
            item_bias_reg=0.01,
            user_vec_reg=0.01,
            item_vec_reg=0.01,
        )
        model.fit(df)

        self.stdout.write(f"Saving model to {model_path}")
        model.save(model_path)
        self.stdout.write(
            self.style.SUCCESS(f"SGD model for {state} saved successfully.")
        )
