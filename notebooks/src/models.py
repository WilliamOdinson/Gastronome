import numpy as np
from sklearn.metrics import mean_squared_error


def compute_approximation_error(num_singular_values, original_matrix, U, S, Vt):
    """
    Calculate the approximation error after reconstructing the matrix using the first num_singular_values singular values.

    Args:
        num_singular_values (int): Number of singular values used
        original_matrix (ndarray): Original matrix
        U (ndarray): Left singular matrix obtained from singular value decomposition
        S (ndarray): Singular value matrix obtained from singular value decomposition
        Vt (ndarray): Transposed right singular matrix obtained from singular value decomposition

    Returns:
        float: Mean squared approximation error
    """
    reconstructed_matrix = np.dot(U[:, :num_singular_values], np.dot(
        S[:num_singular_values, :num_singular_values], Vt[:num_singular_values, :]))
    non_zero_indices = np.where(original_matrix > 0)
    difference = original_matrix[non_zero_indices] - \
        reconstructed_matrix[non_zero_indices]
    return np.linalg.norm(difference)**2 / difference.shape[1]


def compute_global_user_item_bias(rating_matrix):
    """
    Calculate the global bias for users and items, and return the bias-removed rating matrix.

    Args:
        rating_matrix (scipy.sparse matrix): User-item rating matrix

    Returns:
        tuple: A tuple containing the user bias, item bias, and the bias-removed rating matrix
    """
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



def compute_similarity_matrix(rating_matrix, axis='users'):
    """
    Compute the cosine similarity matrix for users or items.

    Args:
        rating_matrix (scipy.sparse matrix): User-item rating matrix
        axis (str): 'users' means computing similarity between users, 'items' means computing similarity between items

    Returns:
        numpy.matrix: Cosine similarity matrix
    """
    if axis == 'users':
        similarity_matrix = rating_matrix * rating_matrix.transpose()
    else:
        similarity_matrix = rating_matrix.transpose() * rating_matrix

    dense_similarity_matrix = similarity_matrix.todense() + 1e-8
    norm_array = np.sqrt(np.diag(dense_similarity_matrix))

    return dense_similarity_matrix / norm_array / norm_array.reshape(-1, 1)



def predict_top_k(rating_matrix, similarity_matrix, kind='user', k=40):
    """
    Perform Top-K prediction using the cosine similarity matrix.

    Args:
        rating_matrix (numpy.ndarray): User-item rating matrix
        similarity_matrix (numpy.matrix): Cosine similarity matrix
        kind (str): 'user' means user-based prediction, 'item' means item-based prediction
        k (int): Select Top-K similar users or items for prediction

    Returns:
        numpy.ndarray: Predicted rating matrix
    """
    predictions = np.zeros(rating_matrix.shape)

    if kind == 'user':
        user_bias = np.mean(rating_matrix, axis=1)
        rating_matrix_adjusted = (
            rating_matrix - np.tile(user_bias, (rating_matrix.shape[1], 1)).T).copy()

        for i in range(rating_matrix.shape[0]):
            top_k_users = np.argsort(similarity_matrix[:, i])[:-k-1:-1]
            predictions[i] = np.dot(similarity_matrix[i, top_k_users], rating_matrix_adjusted[top_k_users, :]
                                    ) / np.sum(np.abs(similarity_matrix[i, top_k_users]))

        predictions += np.tile(user_bias, (rating_matrix.shape[1], 1)).T

    else:
        item_bias = np.mean(rating_matrix, axis=0)
        rating_matrix_adjusted = (
            rating_matrix - np.tile(item_bias, (rating_matrix.shape[0], 1))).copy()

        for j in range(rating_matrix.shape[1]):
            top_k_items = np.argsort(similarity_matrix[:, j])[:-k-1:-1]
            predictions[:, j] = np.dot(similarity_matrix[top_k_items, j].T, rating_matrix_adjusted[:,
                                       top_k_items].T) / np.sum(np.abs(similarity_matrix[top_k_items, j]))

        predictions += np.tile(item_bias, (rating_matrix.shape[0], 1))

    return predictions


def calculate_mse(predictions, actual_ratings):
    """
    Calculate the MSE between the predicted rating matrix and the actual rating matrix.

    Args:
        predictions (numpy.ndarray): Predicted rating matrix
        actual_ratings (numpy.ndarray): Actual rating matrix

    Returns:
        float: MSE
    """
    # Ignore entries with a rating of zero
    non_zero_indices = actual_ratings.nonzero()
    predictions = predictions[non_zero_indices].flatten()
    actual_ratings = actual_ratings[non_zero_indices].flatten()

    return mean_squared_error(predictions, actual_ratings)



def als(ratings_matrix, num_features=40, user_regularization=0, item_regularization=0, iterations=10):
    """
    Use alternating least squares algorithm to compute user and item feature vectors.

    Args:
        ratings_matrix (array-like): User-item rating matrix.
        num_features (int, optional): Dimension of the feature vectors, default is 40.
        user_regularization (float, optional): User regularization parameter to prevent overfitting, default is 0.
        item_regularization (float, optional): Item regularization parameter, also used to prevent overfitting, default is 0.
        iterations (int, optional): Number of iterations, default is 10.

    Returns:
        array-like: Predicted user-item rating matrix.
    """
    ratings_matrix = ratings_matrix.T

    user_vec = np.random.rand(ratings_matrix.shape[1], num_features).T
    res_vec = np.random.rand(ratings_matrix.shape[0], num_features).T

    for i in range(iterations):
        for u in range(ratings_matrix.shape[1]):
            user_vec[:, u] = np.linalg.solve(np.dot(res_vec, res_vec.T) + user_regularization * np.eye(
                res_vec.shape[0]), np.dot(res_vec, ratings_matrix[:, u]))
        for r in range(ratings_matrix.shape[0]):
            res_vec[:, r] = np.linalg.solve(np.dot(user_vec, user_vec.T) + item_regularization * np.eye(
                user_vec.shape[0]), np.dot(user_vec, ratings_matrix[r, :].T))

    return np.dot(res_vec.T, user_vec).T



def sgd_with_bias_correction(rating_matrix, num_features=40, user_bias_reg=0.01, item_bias_reg=0.01,
                             user_vector_reg=0.01, item_vector_reg=0.01, learning_rate=1e-3, iterations=200):
    """
    Perform matrix factorization using stochastic gradient descent with bias correction, learning user and item biases and latent vectors.

    Args:
        rating_matrix (numpy.ndarray): User-item rating matrix
        num_features (int): Number of latent features
        user_bias_reg (float): Regularization parameter for user bias
        item_bias_reg (float): Regularization parameter for item bias
        user_vector_reg (float): Regularization parameter for user vectors
        item_vector_reg (float): Regularization parameter for item vectors
        learning_rate (float): Learning rate
        iterations (int): Number of iterations

    Returns:
        tuple: Predicted rating matrix, error array, user latent vectors, item latent vectors
    """
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
        learning_rate = 1.0 / (100 + 0.01 * iteration)
        np.random.shuffle(training_indices)

        temp_error_array = np.zeros(len(training_indices))

        for datapoint_idx, idx in enumerate(training_indices):
            user = non_zero_user_indices[idx]
            item = non_zero_item_indices[idx]

            prediction = global_bias + \
                user_bias[user] + item_bias[item] + \
                np.dot(user_vectors[user, :], item_vectors[item, :].T)
            error = rating_matrix[user, item] - prediction
            temp_error_array[datapoint_idx] += error**2

            if iteration > 0:
                user_bias[user] += learning_rate * \
                    (error - user_bias_reg * user_bias[user])
                item_bias[item] += learning_rate * \
                    (error - item_bias_reg * item_bias[item])
                user_vectors[user, :] += learning_rate * \
                    (error * item_vectors[item, :] -
                     user_vector_reg * user_vectors[user, :])
                item_vectors[item, :] += learning_rate * \
                    (error * user_vectors[user, :] -
                     item_vector_reg * item_vectors[item, :])

        error_array[iteration] = np.mean(temp_error_array)

    predictions = global_bias + \
        user_bias[:, np.newaxis] + item_bias[np.newaxis, :] + \
        np.dot(user_vectors, item_vectors.T)
    predictions[predictions > 5] = 5
    predictions[predictions < 0] = 0

    return predictions, error_array, user_vectors, item_vectors


def concatenate_user_item_vectors(user_vectors, item_vectors, rating_matrix):
    """
    Concatenate user vectors and item vectors, and return a matrix containing nonzero ratings.

    Args:
        user_vectors (numpy.ndarray): User latent vector matrix (num_users x num_features)
        item_vectors (numpy.ndarray): Item latent vector matrix (num_items x num_features)
        rating_matrix (numpy.ndarray): User-item rating matrix

    Returns:
        numpy.ndarray: Matrix containing user vectors, item vectors, and corresponding ratings
    """
    non_zero_indices = rating_matrix.nonzero()
    user_vectors_non_zero = user_vectors[non_zero_indices[0]]
    item_vectors_non_zero = item_vectors[non_zero_indices[1]]
    ratings_non_zero = rating_matrix[non_zero_indices].reshape(-1, 1)

    concatenated_matrix = np.concatenate(
        (user_vectors_non_zero, item_vectors_non_zero, ratings_non_zero), axis=1)

    return concatenated_matrix
