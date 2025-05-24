from abc import ABC, abstractmethod
from typing import List, Tuple
import pandas as pd
import pathlib
import joblib
import numpy as np


class BaseRecommender(ABC):
    """Unified abstract base class for all recommender models"""

    @abstractmethod
    def fit(self, ratings_df: pd.DataFrame) -> "BaseRecommender":
        """Train the model on a ratings DataFrame"""
        pass

    @abstractmethod
    def predict(self, user_id: str, n: int = 10) -> List[Tuple[str, float]]:
        """Return top-n recommendations (business_id, score) for the given user"""
        pass

    @abstractmethod
    def predict_matrix(self) -> np.ndarray:
        """Return the full user-item score prediction matrix"""
        pass

    def save(self, path: str | pathlib.Path):
        """Serialize the entire model to the specified path (.pkl)"""
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str | pathlib.Path):
        """Deserialize and return a trained model from disk"""
        obj = joblib.load(path)
        if not isinstance(obj, cls):
            raise TypeError(f"The object in the file is not an instance of {cls.__name__}")
        return obj

    @abstractmethod
    def predict_user(self, user_id: str) -> np.ndarray:
        """
        Return a 1-D score vector for all items.
        Cold-start users MAY return zeros.
        """
        pass
