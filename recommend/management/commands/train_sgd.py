from django.core.management.base import BaseCommand
from pathlib import Path
import pandas as pd

from recommend.algorithm.sgd_recommender import SGDRecommender


class Command(BaseCommand):
    help = "Train and save SGD recommendation model for a specific city"

    def add_arguments(self, parser):
        parser.add_argument(
            "--city",
            type=str,
            default="Philadelphia",
            help="City to filter Yelp reviews for (default: Philadelphia)",
        )

    def handle(self, *args, **options):
        city = options["city"]
        city_lower = city.lower()

        BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
        csv_path = BASE_DIR / "database" / "Yelp_final.csv"

        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
            return

        model_dir = BASE_DIR / "assets" / "weights" / "sgd"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / f"sgd_{city_lower}.pkl"

        self.stdout.write(f"Loading data from: {csv_path}")
        df = pd.read_csv(csv_path)

        self.stdout.write(f"Training SGD model for: {city}")
        model = SGDRecommender(
            k=40,
            iterations=200,
            city=city,
            min_user_review=10,
            learning_rate=1e-3,
            user_bias_reg=0.01,
            item_bias_reg=0.01,
            user_vec_reg=0.01,
            item_vec_reg=0.01,
        )
        model.fit(df)

        self.stdout.write(f"Saving model to: {model_path}")
        model.save(model_path)

        self.stdout.write(
            self.style.SUCCESS(
                f"SGD model for {city} saved to {model_path} successfully."))
