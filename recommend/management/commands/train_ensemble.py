from django.core.management.base import BaseCommand
from pathlib import Path
import pandas as pd
import numpy as np

from recommend.algorithm.als_recommender import ALSRecommender
from recommend.algorithm.sgd_recommender import SGDRecommender
from recommend.algorithm.svd_recommender import SVDRecommender
from recommend.algorithm.ensemble_recommender import EnsembleRecommender
from recommend.algorithm.utils import get_clean_df, get_sparse_matrix


class Command(BaseCommand):
    help = "Train and save ensemble recommender using ALS, SGD, and SVD base models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--city",
            type=str,
            default="Philadelphia",
            help="Target city (default: Philadelphia)"
        )
        parser.add_argument(
            "--no-cache",
            action="store_true",
            help="Disable caching the full prediction matrix (saves space, slower inference)"
        )

    def handle(self, *args, **options):
        city = options["city"]
        city_lower = city.lower()
        use_cache = not options["no_cache"]

        BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
        csv_path = BASE_DIR / "database" / "Yelp_final.csv"
        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
            return

        df = pd.read_csv(csv_path)
        df = df[df.city == city]

        self.stdout.write("Preparing rating matrix...")
        clean_df = get_clean_df(df, cols=["user_id", "business_id", "stars"], min_user_review=10)
        sparse_info = get_sparse_matrix(clean_df)
        rating_matrix = sparse_info["matrix"].toarray()
        non_zero_indices = sparse_info["matrix"].nonzero()

        self.stdout.write("Loading base recommenders...")
        model_dir = BASE_DIR / "assets" / "weights"
        als = ALSRecommender.load(model_dir / "als" / f"als_{city_lower}.pkl")
        sgd = SGDRecommender.load(model_dir / "sgd" / f"sgd_{city_lower}.pkl")
        svd = SVDRecommender.load(model_dir / "svd" / f"svd_{city_lower}.pkl")

        self.stdout.write("Fitting ensemble model...")
        ensemble = EnsembleRecommender(
            base_models={"als": als, "sgd": sgd, "svd": svd},
            regressor_type="ridge",
            alpha=1e3,
            use_cache=use_cache
        )
        ensemble.fit(rating_matrix=rating_matrix, non_zero_indices=non_zero_indices)

        output_path = model_dir / f"ensemble_{city_lower}.pkl"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ensemble.save(output_path)

        self.stdout.write(self.style.SUCCESS(f"Ensemble model saved to {output_path}"))
