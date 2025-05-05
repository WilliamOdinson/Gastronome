import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Dict
import joblib

from .base import BaseRecommender
from .utils import get_clean_df, get_sparse_matrix, sgd_with_bias_correction, calculate_mse, concatenate_user_item_vectors

class SGDRecommender(BaseRecommender):
    """
    Bias-corrected matrix factorization using Stochastic Gradient Descent.
    """

    def __init__(self,
                 k: int = 40,
                 iterations: int = 200,
                 city: str | None = None,
                 min_user_review: int = 10,
                 learning_rate: float = 1e-3,
                 user_bias_reg: float = 0.01,
                 item_bias_reg: float = 0.01,
                 user_vec_reg: float = 0.01,
                 item_vec_reg: float = 0.01):
        self.k = k
        self.iterations = iterations
        self.city = city
        self._min_user_review = min_user_review

        # SGD hyperparameters
        self.learning_rate = learning_rate
        self.user_bias_reg = user_bias_reg
        self.item_bias_reg = item_bias_reg
        self.user_vec_reg = user_vec_reg
        self.item_vec_reg = item_vec_reg

        # Learned parameters
        self.user_map: Dict[str, int] = {}
        self.item_map: Dict[str, int] = {}
        self._item_map_inv: Dict[int, str] = {}

        self.global_bias: float = 0.0
        self.user_vectors: np.ndarray | None = None
        self.item_vectors: np.ndarray | None = None

    def fit(self, ratings_df: pd.DataFrame) -> "SGDRecommender":
        """
        Train the recommender using bias-corrected SGD.
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

        R_dense = R_csr.toarray()

        preds, _, self.user_vectors, self.item_vectors, self.user_bias, self.item_bias = sgd_with_bias_correction(
            rating_matrix=R_dense,
            num_features=self.k,
            iterations=self.iterations,
            learning_rate=self.learning_rate,
            user_bias_reg=self.user_bias_reg,
            item_bias_reg=self.item_bias_reg,
            user_vector_reg=self.user_vec_reg,
            item_vector_reg=self.item_vec_reg,
            adaptive_lr=True,
            lr_schedule=None
        )

        # Global average used for cold-start users
        self.global_bias = np.mean(R_dense[R_dense != 0])
        return self

    def predict(self, user_id: str, n: int = 10) -> List[Tuple[str, float]]:
        """
        Recommend top-n items for a given user.
        """
        if self.user_vectors is None or self.item_vectors is None:
            raise RuntimeError("Model has not been fitted.")

        if user_id not in self.user_map:
            return []

        u_idx = self.user_map[user_id]
        scores = (self.global_bias
                  + self.user_bias[u_idx]
                  + self.item_bias.ravel()
                  + self.user_vectors[u_idx] @ self.item_vectors.T)
        
        top_idx = np.argsort(scores)[-n:][::-1]
        return [(self._item_map_inv[int(j)], float(scores[j])) for j in top_idx]

    def save(self, path: str | Path) -> None:
        """
        Save the trained model to disk.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path, compress=("xz", 3))

    @classmethod
    def load(cls, path: str | Path) -> "SGDRecommender":
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
        if self.user_vectors is None or self.item_vectors is None:
            raise RuntimeError("Model has not been fitted.")
        return (self.global_bias
                + self.user_bias[:, np.newaxis]
                + self.item_bias[np.newaxis, :]
                + self.user_vectors @ self.item_vectors.T)
