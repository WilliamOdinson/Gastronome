import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Literal

import joblib
from sklearn.linear_model import LinearRegression, Ridge

from .base import BaseRecommender


class EnsembleRecommender(BaseRecommender):
    """
    Linear ensemble of pre-trained base recommenders.
    """

    def __init__(
        self,
        base_models: Dict[str, BaseRecommender],
        regressor_type: Literal["linear", "ridge"] = "ridge",
        alpha: float = 1e3,
        use_cache: bool = True,
    ):
        if not base_models:
            raise ValueError("`base_models` cannot be empty.")

        self.base_models = base_models
        self.regressor_type = regressor_type
        self.alpha = alpha
        self.use_cache = use_cache

        self.model = None
        self._pred_full: np.ndarray | None = None

        first = next(iter(base_models.values()))
        self.user_map = first.user_map
        self.item_map = first.item_map
        self._item_map_inv = first.item_map_inv

    def fit(
        self,
        rating_matrix: np.ndarray,
        non_zero_indices: Tuple[np.ndarray, np.ndarray],
    ) -> "EnsembleRecommender":
        """
        Train the ensemble regressor on observed ratings.
        """
        X_train = np.column_stack([
            model.predict_matrix()[non_zero_indices].reshape(-1, 1)
            for model in self.base_models.values()
        ])
        y_train = rating_matrix[non_zero_indices].ravel()

        if self.regressor_type == "ridge":
            self.model = Ridge(alpha=self.alpha, fit_intercept=True)
        else:
            self.model = LinearRegression(fit_intercept=True)

        self.model.fit(X_train, y_train)

        if self.use_cache:
            self._cache_full_prediction()

        return self

    def _cache_full_prediction(self) -> None:
        """
        Precompute and cache full prediction matrix.
        """
        if self.model is None:
            raise RuntimeError("Ensemble regressor not trained.")

        base_preds = np.stack(
            [m.predict_matrix() for m in self.base_models.values()],
            axis=0
        )
        weights = self.model.coef_.reshape(-1, 1, 1)
        self._pred_full = (weights * base_preds).sum(axis=0) + self.model.intercept_

    def predict(self, user_id: str, n: int = 10) -> List[Tuple[str, float]]:
        """
        Return top-n recommendations for a user.
        """
        if self._pred_full is None:
            raise RuntimeError("Prediction matrix not cached. Enable use_cache.")

        if user_id not in self.user_map:
            return []

        u_idx = self.user_map[user_id]
        scores = self._pred_full[u_idx]
        top_idx = np.argsort(scores)[-n:][::-1]
        return [(self._item_map_inv[int(j)], float(scores[j])) for j in top_idx]

    def predict_matrix(self) -> np.ndarray:
        if self._pred_full is None:
            raise RuntimeError("Prediction matrix not available.")
        return self._pred_full

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not self.use_cache:
            pred_cache = self._pred_full
            self._pred_full = None
            joblib.dump(self, path, compress=("xz", 3))
            self._pred_full = pred_cache
        else:
            joblib.dump(self, path, compress=("xz", 3))

    @classmethod
    def load(cls, path: str | Path) -> "EnsembleRecommender":
        obj = joblib.load(path)
        if not isinstance(obj, cls):
            raise TypeError(f"File does not contain {cls.__name__}")
        return obj

    @property
    def item_map_inv(self) -> Dict[int, str]:
        if not self._item_map_inv:
            raise RuntimeError("Model not fitted.")
        return self._item_map_inv
