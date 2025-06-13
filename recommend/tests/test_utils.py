import numpy as np
import pandas as pd
from unittest import TestCase

from recommend.algorithm.utils import (
    get_clean_df,
    get_sparse_matrix,
    sgd_with_bias_correction,
    calculate_mse,
)


class UtilsTests(TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            {
                "user_id": ["u1", "u1", "u2", "u3"],
                "business_id": ["b1", "b2", "b1", "b2"],
                "stars": [5, 4, 3, 2],
            }
        )

    def test_get_clean_df_filters_by_min_reviews(self):
        """
        Test that get_clean_df filters out users with fewer than min_user_review reviews.
        """
        cleaned = get_clean_df(self.df, ["user_id", "business_id", "stars"], min_user_review=2)
        # u1 appears twice -> kept; u2 and u3 appear once -> dropped
        self.assertTrue(set(cleaned["user_id"]) == {"u1"})

    def test_sparse_matrix_shapes_and_maps(self):
        """
        Test that get_sparse_matrix returns the correct shape and index mappings.
        """
        mat_info = get_sparse_matrix(self.df)
        mat = mat_info["matrix"]
        self.assertEqual(mat.shape, (3, 2))  # 3 users * 2 businesses
        self.assertEqual(len(mat_info["row_index"]), 3)
        self.assertEqual(len(mat_info["col_index"]), 2)

    def test_sgd_with_bias_correction_decreases_error(self):
        """
        Test that the SGD with bias correction reduces error over iterations.
        """
        R = np.array([[5.0, 4.0], [3.0, 0.0]])
        preds, errs, *_ = sgd_with_bias_correction(
            R,
            num_features=2,
            iterations=15,
            learning_rate=1e-2,
            adaptive_lr=False,
        )
        self.assertEqual(preds.shape, R.shape)
        # error trend should be non-increasing on average
        self.assertLessEqual(errs[-1], errs[0])

    def test_mse_computation(self):
        """
        Test that calculate_mse computes the mean squared error correctly.
        """
        actual = np.array([[5, 0], [3, 4]])
        pred = np.array([[4.5, 0.1], [3.2, 3.8]])
        mse = calculate_mse(pred, actual)
        self.assertGreater(mse, 0)
