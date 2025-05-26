import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.metrics import mean_squared_error
from typing import Dict, Tuple, Callable, Optional


def get_clean_df(df: pd.DataFrame,
                 cols: list[str],
                 min_user_review: int = 30,
                 min_res_review: int = 0) -> pd.DataFrame:
    df_new = df[cols].dropna()

    user_col = cols[0]
    item_col = cols[1]

    item_counts = df_new[item_col].value_counts()
    kept_items = item_counts[item_counts >= min_res_review].index
    df_new = df_new[df_new[item_col].isin(kept_items)]

    user_counts = df_new[user_col].value_counts()
    kept_users = user_counts[user_counts >= min_user_review].index
    df_clean = df_new[df_new[user_col].isin(kept_users)]

    return df_clean.reset_index(drop=True)


def get_sparse_matrix(df):
    unique_users = list(df['user_id'].unique())
    unique_businesses = list(df['business_id'].unique())

    user_map = {uid: i for i, uid in enumerate(unique_users)}
    item_map = {bid: j for j, bid in enumerate(unique_businesses)}

    user_indices = [user_map[uid] for uid in df['user_id']]
    business_indices = [item_map[bid] for bid in df['business_id']]
    ratings = df['stars'].tolist()

    sparse_matrix = csr_matrix(
        (ratings, (user_indices, business_indices)),
        shape=(len(user_map), len(item_map))
    )

    return {
        "matrix": sparse_matrix,
        "row_index": user_map,
        "col_index": item_map
    }


def compute_global_user_item_bias(rating_matrix):
    dense_matrix = rating_matrix.todense()
    mask_matrix = (dense_matrix > 0).astype(int)

    # Calculate user bias
    user_bias = np.sum(dense_matrix, axis=1) / np.sum(mask_matrix, axis=1)
    user_bias = np.nan_to_num(user_bias).reshape(-1, 1)

    # Calculate item bias, avoiding division by zero
    item_bias_denominator = np.sum(mask_matrix, axis=0)
    item_bias_denominator[item_bias_denominator == 0] = 1  # Avoid division by zero
    item_bias = np.sum(dense_matrix, axis=0) / item_bias_denominator
    item_bias = np.nan_to_num(item_bias).reshape(1, -1)

    # Calculate the bias-removed rating matrix
    ratings_matrix_no_bias = dense_matrix - \
        np.tile(user_bias, (1, dense_matrix.shape[1])) - \
        np.tile(item_bias, (dense_matrix.shape[0], 1))

    return user_bias, item_bias, ratings_matrix_no_bias


def sgd_with_bias_correction(
    rating_matrix,
    num_features: int = 40,
    user_bias_reg: float = 0.01,
    item_bias_reg: float = 0.01,
    user_vector_reg: float = 0.01,
    item_vector_reg: float = 0.01,
    learning_rate: float = 1e-3,
    iterations: int = 200,
    adaptive_lr: bool = False,
    lr_schedule: Optional[Callable[[int], float]] = None,
):
    num_users, num_items = rating_matrix.shape
    error_array = np.zeros(iterations)

    global_bias = np.mean(rating_matrix[np.where(rating_matrix != 0)])
    user_bias = 0.1 * (2 * (np.random.rand(num_users) - 1))
    item_bias = 0.1 * (2 * (np.random.rand(num_items) - 1))
    user_vectors = 0.1 * (2 * (np.random.rand(num_users, num_features) - 1))
    item_vectors = 0.1 * (2 * (np.random.rand(num_items, num_features) - 1))

    rows, cols = rating_matrix.nonzero()
    training_indices = np.arange(rows.shape[0])

    for iteration in range(iterations):
        lr = (
            lr_schedule(iteration)
            if lr_schedule
            else (1.0 / (100 + 0.01 * iteration) if adaptive_lr else learning_rate)
        )

        np.random.shuffle(training_indices)
        tmp_err = np.zeros(len(training_indices))

        for d_idx, idx in enumerate(training_indices):
            u = rows[idx]
            i = cols[idx]

            pred = (
                global_bias
                + user_bias[u]
                + item_bias[i]
                + np.dot(user_vectors[u], item_vectors[i])
            )
            err = rating_matrix[u, i] - pred
            tmp_err[d_idx] = err * err

            grad_ub = lr * (err - user_bias_reg * user_bias[u])
            grad_ib = lr * (err - item_bias_reg * item_bias[i])
            user_bias[u] += np.clip(grad_ub, -1.0, 1.0)
            item_bias[i] += np.clip(grad_ib, -1.0, 1.0)

            grad_uv = lr * (err * item_vectors[i] - user_vector_reg * user_vectors[u])
            grad_iv = lr * (err * user_vectors[u] - item_vector_reg * item_vectors[i])
            user_vectors[u] += np.clip(grad_uv, -10.0, 10.0)
            item_vectors[i] += np.clip(grad_iv, -10.0, 10.0)

        error_array[iteration] = np.mean(tmp_err)

    predictions = (
        global_bias
        + user_bias[:, None]
        + item_bias[None, :]
        + user_vectors @ item_vectors.T
    )
    predictions = np.clip(predictions, 0, 5)

    return (
        predictions,
        error_array,
        user_vectors,
        item_vectors,
        user_bias,
        item_bias,
    )


def concatenate_user_item_vectors(user_vectors, item_vectors, rating_matrix):
    non_zero_indices = rating_matrix.nonzero()
    user_vectors_non_zero = user_vectors[non_zero_indices[0]]
    item_vectors_non_zero = item_vectors[non_zero_indices[1]]
    ratings_non_zero = rating_matrix[non_zero_indices].reshape(-1, 1)

    concatenated_matrix = np.concatenate(
        (user_vectors_non_zero, item_vectors_non_zero, ratings_non_zero), axis=1)

    return concatenated_matrix


def calculate_mse(predictions, actual_ratings):
    non_zero_indices = actual_ratings.nonzero()
    predictions = predictions[non_zero_indices].flatten()
    actual_ratings = actual_ratings[non_zero_indices].flatten()

    return mean_squared_error(predictions, actual_ratings)
