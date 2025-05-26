from pathlib import Path

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand

from recommend.algorithm.als_recommender import ALSRecommender
from recommend.algorithm.sgd_recommender import SGDRecommender
from recommend.algorithm.svd_recommender import SVDRecommender
from recommend.algorithm.ensemble_recommender import EnsembleRecommender
from recommend.algorithm.utils import get_clean_df, get_sparse_matrix


class Command(BaseCommand):
    """
    Train and save an ensemble recommender (ALS + SGD + SVD) for a single state.
    """

    help = "Train ensemble model for a given state (default: PA)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--state",
            type=str,
            default="PA",
            help="Target US state two-letter code (e.g. PA, CA)",
        )
        parser.add_argument(
            "--no-cache",
            action="store_true",
            help="Disable caching of full prediction matrix",
        )

    def handle(self, *args, **options):
        state = options["state"].upper()
        state_lower = state.lower()
        use_cache = not options["no_cache"]

        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        csv_path = base_dir / "database" / "Yelp_final.csv"
        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
            return

        df = pd.read_csv(csv_path)
        df = df[df.state == state]

        self.stdout.write("Preparing rating matrix...")
        clean_df = get_clean_df(
            df, cols=["user_id", "business_id", "stars"], min_user_review=10
        )
        sparse_info = get_sparse_matrix(clean_df)
        rating_matrix = sparse_info["matrix"].toarray()
        non_zero_idx = sparse_info["matrix"].nonzero()

        model_dir = base_dir / "assets" / "weights"
        als = ALSRecommender.load(model_dir / "als" / f"als_{state_lower}.pkl")
        sgd = SGDRecommender.load(model_dir / "sgd" / f"sgd_{state_lower}.pkl")
        svd = SVDRecommender.load(model_dir / "svd" / f"svd_{state_lower}.pkl")

        self.stdout.write("Fitting ensemble model...")
        ensemble = EnsembleRecommender(
            base_models={"als": als, "sgd": sgd, "svd": svd},
            regressor_type="ridge",
            alpha=1e3,
            use_cache=use_cache,
        )
        ensemble.fit(rating_matrix=rating_matrix, non_zero_indices=non_zero_idx)

        out_path = model_dir / f"ensemble_{state_lower}.pkl"
        ensemble.save(out_path)
        self.stdout.write(
            self.style.SUCCESS(f"Ensemble model saved to {out_path}")
        )
