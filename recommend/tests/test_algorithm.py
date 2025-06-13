import json
import tempfile
import types
from pathlib import Path
from unittest import TestCase

import numpy as np
import pandas as pd

from recommend.algorithm.als_recommender import ALSRecommender
from recommend.algorithm.sgd_recommender import SGDRecommender
from recommend.algorithm.svd_recommender import SVDRecommender
from recommend.algorithm.ensemble_recommender import EnsembleRecommender
from recommend.algorithm.utils import (
    get_clean_df,
    get_sparse_matrix,
    sgd_with_bias_correction,
)

DF = pd.DataFrame(
    {
        "user_id": ["u1", "u1", "u2", "u2", "u3", "u3"],
        "business_id": ["b1", "b2", "b1", "b3", "b2", "b3"],
        "stars": [5, 4, 3, 2, 4, 5],
        "state": ["PA"] * 6,
    }
)


class ALSRecommenderTests(TestCase):
    def setUp(self):
        self.model = ALSRecommender(k=2, iterations=3, min_user_review=0, random_state=0)

    def test_predict_before_fit_raises(self):
        """
        Test that calling predict before fitting the model raises an error.
        """
        with self.assertRaises(RuntimeError):
            self.model.predict("u1", 2)

    def test_fit_and_predict(self):
        """
        Test that fitting the model works and that predictions return the expected format.
        """
        self.model.fit(DF)
        recs = self.model.predict("u1", n=2)
        self.assertEqual(len(recs), 2)
        # Should return business_id strings
        self.assertTrue(all(isinstance(bid, str) for bid, _ in recs))

    def test_unknown_user_returns_empty(self):
        """
        Test that predicting for a user not in the training data returns an empty list.
        """
        self.model.fit(DF)
        self.assertEqual(self.model.predict("ux", 5), [])

    def test_save_and_load_roundtrip(self):
        """
        Test that saving and loading the model works correctly.
        """
        self.model.fit(DF)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "als.pkl"
            self.model.save(p)
            loaded = ALSRecommender.load(p)
        self.assertEqual(
            loaded.predict("u1", 3),
            self.model.predict("u1", 3),
        )


class SGDRecommenderTests(TestCase):
    def setUp(self):
        self.sgd = SGDRecommender(
            k=2,
            iterations=10,
            learning_rate=1e-2,
            min_user_review=0,
        )

    def test_fit_and_matrix_shapes(self):
        """
        Test that fitting the model produces a matrix of the expected shape.
        """
        self.sgd.fit(DF)
        mat = self.sgd.predict_matrix()
        self.assertEqual(mat.shape, (3, 3))  # 3 users * 3 items

    def test_top_n_recommend(self):
        """
        Test that top_n_recommend returns the correct number of recommendations.
        """
        self.sgd.fit(DF)
        top = self.sgd.predict("u2", 1)
        self.assertEqual(len(top), 1)

    def test_cold_start_user_returns_empty(self):
        """
        Test that predicting for a user not in the training data returns an empty list.
        """
        self.sgd.fit(DF)
        self.assertEqual(self.sgd.predict("new_user", 2), [])


class SVDRecommenderTests(TestCase):
    def setUp(self):
        self.svd = SVDRecommender(k=2, min_user_review=0)

    def test_predict_user_vector_size(self):
        """
        Test that the user vector size matches the number of items after fitting.
        """
        self.svd.fit(DF)
        vec = self.svd.predict_user("u3")
        self.assertEqual(vec.size, len(self.svd.item_map))

    def test_item_map_inv_requires_fit(self):
        """
        Test that accessing item_map_inv before fitting raises an error.
        """
        with self.assertRaises(RuntimeError):
            _ = self.svd.item_map_inv


class EnsembleRecommenderTests(TestCase):
    def setUp(self):
        # Base models
        self.als = ALSRecommender(k=2, iterations=2, min_user_review=0).fit(DF)
        self.sgd = SGDRecommender(k=2, iterations=5, min_user_review=0).fit(DF)

        # Target rating matrix + indices
        mat = get_sparse_matrix(get_clean_df(DF, ["user_id", "business_id", "stars"], 0))[
            "matrix"
        ].toarray()
        nz = np.nonzero(mat)

        self.ensemble = EnsembleRecommender(
            {"als": self.als, "sgd": self.sgd},
            regressor_type="linear",
            use_cache=True,
        ).fit(mat, nz)

    def test_predict_seen_user(self):
        """
        Test that predicting for a user with seen items returns the expected number of recommendations.
        """
        recs = self.ensemble.predict("u1", n=2)
        self.assertEqual(len(recs), 2)

    def test_predict_cold_start_user(self):
        """
        Test that predicting for a cold start user returns the expected number of recommendations.
        """
        cold = self.ensemble.predict("uxxx", n=3)
        self.assertEqual(len(cold), 3)

    def test_predict_matrix_cached(self):
        """
        Test that the predict_matrix method returns a matrix of the expected shape.
        """
        m = self.ensemble.predict_matrix()
        self.assertEqual(m.shape, (3, 3))

    def test_save_without_cache_flag(self):
        """
        Test that saving and loading the ensemble recommender works without cache.
        """
        mat = self.ensemble.predict_matrix()
        no_cache = EnsembleRecommender(
            {"als": self.als}, regressor_type="linear", use_cache=False
        )
        no_cache.fit(mat, np.nonzero(mat))
        with tempfile.TemporaryDirectory() as td:
            fp = Path(td) / "ens.pkl"
            no_cache.save(fp)
            loaded = EnsembleRecommender.load(fp)
        self.assertIsInstance(loaded, EnsembleRecommender)

    def test_empty_base_models_raises(self):
        """
        Test that initializing EnsembleRecommender with an empty base models dict raises ValueError.
        """
        with self.assertRaises(ValueError):
            EnsembleRecommender({}, "linear")
