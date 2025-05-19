from django.core.management.base import BaseCommand
from pathlib import Path
import pandas as pd

from recommend.algorithm.svd_recommender import SVDRecommender


class Command(BaseCommand):
    help = "Train and save SVD recommendation model for a specific city"

    def add_arguments(self, parser):
        parser.add_argument(
            "--city",
            type=str,
            default="Philadelphia",
            help="City to train SVD model for (default: Philadelphia)",
        )

    def handle(self, *args, **options):
        city = options["city"]
        city_lower = city.lower()

        BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
        csv_path = BASE_DIR / "database" / "Yelp_final.csv"

        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
            return

        model_dir = BASE_DIR / "assets" / "weights" / "svd"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / f"svd_{city_lower}.pkl"

        self.stdout.write(f"Loading data from: {csv_path}")
        df = pd.read_csv(csv_path)

        self.stdout.write(f"Training SVD model for: {city}")

        model = SVDRecommender(
            k=10,
            city=city,
            min_user_review=10,
        )
        model.fit(df)
        model.save(model_path)

        self.stdout.write(
            self.style.SUCCESS(
                f"SVD model for {city} saved to {model_path} successfully."))
