import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Dict
import joblib

from recommend.algorithm.base import BaseRecommender
from recommend.algorithm.utils import get_clean_df, get_sparse_matrix, compute_global_user_item_bias


class SVDRecommender(BaseRecommender):
    """
    Bias-corrected Truncated SVD recommender.
    """

    def __init__(self, k: int = 10,
                 state: str | None = None,
                 min_user_review: int = 10) -> None:
        self.k = k
        self.state = state
        self._min_user_review = min_user_review

        # ID mappings
        self.user_map: Dict[str, int] = {}
        self.item_map: Dict[str, int] = {}
        self._item_map_inv: Dict[int, str] = {}

        # Bias terms
        self.global_bias: float = 0.0
        self.user_bias: np.ndarray | None = None
        self.item_bias: np.ndarray | None = None

        # SVD components
        self.U_k: np.ndarray | None = None
        self.S_k: np.ndarray | None = None
        self.Vt_k: np.ndarray | None = None

        # Optional: full prediction matrix cache
        self._pred_full: np.ndarray | None = None

    def fit(self, ratings_df: pd.DataFrame) -> "SVDRecommender":
        """
        Train the model using bias-corrected SVD.
        """
        if self.state:
            ratings_df = ratings_df[ratings_df.state == self.state]

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

        R_dense = R_csr.todense()

        # Compute global bias
        self.global_bias = R_dense.sum() / R_csr.nnz
        R_centered = R_dense - self.global_bias

        # Remove user and item bias
        self.user_bias, self.item_bias, R_no_bias = compute_global_user_item_bias(R_csr)
        R_no_bias = np.asarray(R_no_bias)

        # Perform truncated SVD
        U, s, Vt = np.linalg.svd(R_no_bias, full_matrices=False)
        self.U_k = U[:, :self.k]
        self.S_k = np.diag(s[:self.k])
        self.Vt_k = Vt[:self.k, :]

        recon = self.U_k @ self.S_k @ self.Vt_k
        self._pred_full = recon + self.global_bias + self.user_bias + self.item_bias

        return self

    def predict(self, user_id: str, n: int = 10) -> List[Tuple[str, float]]:
        """
        Return top-n item recommendations for a given user.
        """
        if self.U_k is None:
            raise RuntimeError("Model has not been fitted.")

        if user_id not in self.user_map:
            return []

        u_idx = self.user_map[user_id]
        scores = (
            self.U_k[u_idx, :].reshape(1, -1) @ self.S_k @ self.Vt_k
            + self.global_bias
            + self.user_bias[u_idx]
            + self.item_bias
        ).ravel()

        top_idx = np.argsort(scores)[-n:][::-1]
        return [(self._item_map_inv[int(j)], float(scores[j])) for j in top_idx]

    def save(self, path: str | Path) -> None:
        """
        Save model to disk (excluding cached prediction matrix).
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        pred_cache = self._pred_full
        self._pred_full = None
        joblib.dump(self, path, compress=("xz", 3))
        self._pred_full = pred_cache

    @classmethod
    def load(cls, path: str | Path) -> "SVDRecommender":
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
        if self._pred_full is None:
            if self.U_k is None or self.S_k is None or self.Vt_k is None:
                raise RuntimeError("Model has not been fitted.")
            self._pred_full = (
                self.U_k @ self.S_k @ self.Vt_k
                + self.global_bias
                + self.user_bias
                + self.item_bias
            )
        return self._pred_full

    def predict_user(self, user_id: str) -> np.ndarray:
        if self.U_k is None:
            raise RuntimeError("Model not fitted")
        if user_id in self.user_map:
            u = self.user_map[user_id]
            base = (self.U_k[u] @ self.S_k @ self.Vt_k)
            return (base + self.global_bias
                    + self.user_bias[u] + self.item_bias).ravel()
        # cold-start: use global average + item bias
        return (self.global_bias + self.item_bias).ravel()
