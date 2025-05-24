import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Dict
import joblib

from recommend.algorithm.base import BaseRecommender
from recommend.algorithm.utils import get_clean_df, get_sparse_matrix


class ALSRecommender(BaseRecommender):
    """
    Alternating Least Squares recommender.
    """

    def __init__(
        self,
        k: int = 10,
        iterations: int = 5,
        user_reg: float = 1e-3,
        item_reg: float = 1e-3,
        city: str | None = None,
        min_user_review: int = 10,
        random_state: int = 42,
    ):
        self.k = k
        self.iterations = iterations
        self.user_reg = user_reg
        self.item_reg = item_reg
        self.city = city
        self._min_user_review = min_user_review
        self.random_state = random_state

        # ID mappings
        self.user_map: Dict[str, int] = {}
        self.item_map: Dict[str, int] = {}
        self._item_map_inv: Dict[int, str] = {}

        # Latent factor matrices
        self.user_factors: np.ndarray | None = None  # shape: (num_users, k)
        self.item_factors: np.ndarray | None = None  # shape: (num_items, k)

    def fit(self, ratings_df: pd.DataFrame) -> "ALSRecommender":
        """
        Train ALS model from the given rating dataframe.
        """
        if self.city:
            ratings_df = ratings_df[ratings_df.city == self.city]

        clean_df = get_clean_df(
            ratings_df,
            min_user_review=self._min_user_review,
            cols=["user_id", "business_id", "stars"],
        )

        mat_info = get_sparse_matrix(clean_df)
        R_csr = mat_info["matrix"].astype(float)
        self.user_map = mat_info["row_index"]
        self.item_map = mat_info["col_index"]
        self._item_map_inv = {j: bid for bid, j in self.item_map.items()}

        R = R_csr.toarray()

        self.user_factors, self.item_factors = self._als_factorization(
            R,
            k=self.k,
            iterations=self.iterations,
            user_reg=self.user_reg,
            item_reg=self.item_reg,
            seed=self.random_state,
        )

        return self

    def predict(self, user_id: str, n: int = 10) -> List[Tuple[str, float]]:
        """
        Return top-n item recommendations for a given user.
        """
        if self.user_factors is None or self.item_factors is None:
            raise RuntimeError("Model has not been fitted.")

        if user_id not in self.user_map:
            return []

        u_idx = self.user_map[user_id]
        scores = self.user_factors[u_idx] @ self.item_factors.T
        top_idx = np.argsort(scores)[-n:][::-1]

        return [(self._item_map_inv[int(j)], float(scores[j])) for j in top_idx]

    @staticmethod
    def _als_factorization(R: np.ndarray, k: int, iterations: int, user_reg: float,
                           item_reg: float, seed: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Perform ALS matrix factorization.
        Returns user and item latent factor matrices.
        """
        np.random.seed(seed)
        num_users, num_items = R.shape

        user_factors = np.random.rand(num_users, k)
        item_factors = np.random.rand(num_items, k)

        I_k = np.eye(k)

        for _ in range(iterations):
            # Update user factors
            YTY = item_factors.T @ item_factors + user_reg * I_k
            for u in range(num_users):
                user_factors[u] = np.linalg.solve(YTY, item_factors.T @ R[u, :])

            # Update item factors
            XTX = user_factors.T @ user_factors + item_reg * I_k
            for i in range(num_items):
                item_factors[i] = np.linalg.solve(XTX, user_factors.T @ R[:, i])

        return user_factors, item_factors

    def save(self, path: str | Path) -> None:
        """
        Save the trained model to disk.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path, compress=("xz", 3))

    @classmethod
    def load(cls, path: str | Path) -> "ALSRecommender":
        """
        Load a saved model from disk.
        """
        obj = joblib.load(path)
        if not isinstance(obj, cls):
            raise TypeError(f"File does not contain {cls.__name__}")
        return obj

    @property
    def item_map_inv(self) -> Dict[int, str]:
        """
        Return the reverse item ID mapping.
        """
        if not self._item_map_inv:
            raise RuntimeError("Model not fitted.")
        return self._item_map_inv

    def predict_matrix(self) -> np.ndarray:
        if self.user_factors is None or self.item_factors is None:
            raise RuntimeError("Model has not been fitted.")
        return self.user_factors @ self.item_factors.T

    def predict_user(self, user_id: str) -> np.ndarray:
        """
        Return item-score vector for any user.
        If unseen, use mean of user factors.
        """
        if self.user_factors is None or self.item_factors is None:
            raise RuntimeError("Model not fitted")

        if user_id in self.user_map:
            u_vec = self.user_factors[self.user_map[user_id]]
        else:
            u_vec = self.user_factors.mean(axis=0)
        return u_vec @ self.item_factors.T
