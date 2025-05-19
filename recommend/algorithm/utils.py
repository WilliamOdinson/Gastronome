import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.metrics import mean_squared_error
from typing import Dict, Tuple


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


def sgd_with_bias_correction(rating_matrix,
                             num_features=40,
                             user_bias_reg=0.01,
                             item_bias_reg=0.01,
                             user_vector_reg=0.01,
                             item_vector_reg=0.01,
                             learning_rate=1e-3,
                             iterations=200,
                             adaptive_lr: bool = False,
                             lr_schedule: callable = None):
    num_users, num_items = rating_matrix.shape
    error_array = np.zeros(iterations)

    global_bias = np.mean(rating_matrix[np.where(rating_matrix != 0)])
    user_bias = 0.1 * (2 * (np.random.rand(num_users) - 1))
    item_bias = 0.1 * (2 * (np.random.rand(num_items) - 1))
    user_vectors = 0.1 * (2 * (np.random.rand(num_users, num_features) - 1))
    item_vectors = 0.1 * (2 * (np.random.rand(num_items, num_features) - 1))

    training_indices = np.arange(rating_matrix.nonzero()[0].shape[0])
    np.random.shuffle(training_indices)
    non_zero_user_indices = rating_matrix.nonzero()[0]
    non_zero_item_indices = rating_matrix.nonzero()[1]

    for iteration in range(iterations):
        if lr_schedule is not None:
            lr = lr_schedule(iteration)
        elif adaptive_lr:
            lr = 1.0 / (100 + 0.01 * iteration)
        else:
            lr = learning_rate

        np.random.shuffle(training_indices)
        temp_error_array = np.zeros(len(training_indices))

        for datapoint_idx, idx in enumerate(training_indices):
            user = non_zero_user_indices[idx]
            item = non_zero_item_indices[idx]

            prediction = global_bias + user_bias[user] + item_bias[item] + \
                np.dot(user_vectors[user, :], item_vectors[item, :].T)
            error = rating_matrix[user, item] - prediction
            temp_error_array[datapoint_idx] += error**2

            user_bias[user] += lr * (error - user_bias_reg * user_bias[user])
            item_bias[item] += lr * (error - item_bias_reg * item_bias[item])
            user_vectors[user, :] += lr * \
                (error * item_vectors[item, :] - user_vector_reg * user_vectors[user, :])
            item_vectors[item, :] += lr * \
                (error * user_vectors[user, :] - item_vector_reg * item_vectors[item, :])

        error_array[iteration] = np.mean(temp_error_array)

    predictions = global_bias + user_bias[:, np.newaxis] + item_bias[np.newaxis, :] + \
        np.dot(user_vectors, item_vectors.T)
    predictions = np.clip(predictions, 0, 5)

    return predictions, error_array, user_vectors, item_vectors, user_bias, item_bias


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
