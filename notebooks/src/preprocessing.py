import re
import json
import pandas as pd
import numpy as np
from sklearn.base import BaseEstimator
from scipy import sparse
from scipy.sparse import csr_matrix
from sklearn.metrics import accuracy_score

def get_top_m_num_reviews_for_city_and_business(df, m):
    """
    Get the number of businesses counted by city and category, and return the top m results.

    Args:
        df (pd.DataFrame): DataFrame containing business information.
        m (int): Number of top m results to return.

    Returns:
        pd.Series: Series containing the top m counts of businesses by city and category.
    """
    business_city_count = {}
    n = len(df)

    for i in range(n):

        categories = str(df.categories.iloc[i]).split(',')
        city = df.city.iloc[i]
        for category in categories:
            key = (category, city) 
            if key not in business_city_count.keys():
                business_city_count[key] = 1
            else:
                business_city_count[key] += 1

    business_city_count_series = pd.Series(business_city_count)
    business_city_count_series.sort_values(ascending=False, inplace=True)

    return business_city_count_series[:m]



def get_clean_df(df, cols, min_user_review=30, min_res_review=0):
    """
    Clean the data and filter based on minimum number of reviews

    Args:
        df (DataFrame): Original dataframe
        cols (list): List of column names to retain
        min_user_review (int, optional): Minimum number of user reviews, default is 30
        min_res_review (int, optional): Minimum number of business reviews, default is 0

    Returns:
        DataFrame: Cleaned and filtered dataframe
    """
    df_new = df[cols].copy()
    df_new.dropna(axis=0, how='any', inplace=True)
    df_new[cols[1] + '_freq'] = df_new.groupby(cols[1])[cols[1]].transform('count')
    df_clean = df_new[df_new[cols[1] + '_freq'] >= min_res_review]
    df_clean[cols[0] + '_freq'] = df_clean.groupby(cols[0])[cols[0]].transform('count')
    df_clean_2 = df_clean[df_clean[cols[0] + '_freq'] >= min_user_review]

    return df_clean_2



def get_sparsity(sparse_matrix):
    """
    Calculate the sparsity of a sparse matrix

    Args:
        sparse_matrix (csr_matrix): Sparse matrix

    Returns:
        float: Sparsity, represented as the proportion of nonzero elements in the sparse matrix
    """
    density = sparse_matrix.nnz / \
        (sparse_matrix.shape[0] * sparse_matrix.shape[1])
    return 1 - density


def get_sparse_matrix(df):
    """
    Convert dataframe into a sparse rating matrix

    Args:
        df (DataFrame): Dataframe containing users, businesses, and ratings

    Returns:
        csr_matrix: Sparse rating matrix
    """
    unique_users = list(df['user_id'].unique())

    unique_businesses = list(df['business_id'].unique())

    ratings = df['stars'].tolist()

    user_indices = pd.Categorical(df['user_id'], categories=unique_users).codes

    business_indices = pd.Categorical(df['business_id'], categories=unique_businesses).codes

    sparse_matrix = csr_matrix((ratings, (user_indices, business_indices)), shape=(len(unique_users), len(unique_businesses)))
    return sparse_matrix



def train_val_test_split(sparse_matrix, num_review_val=2, num_review_test=2):
    """Split the sparse matrix into training, validation, and test sets

    Args:
        sparse_matrix (csr_matrix): Input sparse matrix
        num_review_val (int, optional): Number of reviews per user for validation. Default is 2.
        num_review_test (int, optional): Number of reviews per user for testing. Default is 2.

    Returns:
        tuple: Sparse matrices for training, validation, and testing
    """
    nonzero_rows, nonzero_cols = sparse_matrix.nonzero()

    sparse_matrix_test = csr_matrix(sparse_matrix.shape)
    sparse_matrix_val = csr_matrix(sparse_matrix.shape)
    sparse_matrix_train = sparse_matrix.copy()

    num_users = sparse_matrix.shape[0]

    for user in range(num_users):
        user_review_indices = nonzero_cols[np.where(nonzero_rows == user)]
        np.random.shuffle(user_review_indices)

        # Split indices for test set and validation set
        test_indices = user_review_indices[-num_review_test:]
        val_indices = user_review_indices[-(num_review_val +
                                            num_review_test):-num_review_test]

        # Assign test set and validation set indices to corresponding sparse matrices
        sparse_matrix_test[user,
                           test_indices] = sparse_matrix[user, test_indices]
        sparse_matrix_val[user, val_indices] = sparse_matrix[user, val_indices]

        # Remove validation and test indices from the training set
        sparse_matrix_train[user, test_indices] = 0
        sparse_matrix_train[user, val_indices] = 0

    # Recreate the training set sparse matrix to remove zero elements
    train_data = np.array(
        sparse_matrix_train[sparse_matrix_train.nonzero()])[0]
    train_rows = sparse_matrix_train.nonzero()[0]
    train_cols = sparse_matrix_train.nonzero()[1]
    matrix_size = sparse_matrix_train.shape

    sparse_matrix_train = csr_matrix(
        (train_data, (train_rows, train_cols)), shape=matrix_size)

    # Ensure no overlap between training, validation, and test sets
    overlap_val_test = sparse_matrix_train.multiply(sparse_matrix_val)
    overlap_all = overlap_val_test.multiply(sparse_matrix_test)

    assert overlap_all.nnz == 0, "There are overlapping elements between training, validation, and test sets"

    return sparse_matrix_train, sparse_matrix_val, sparse_matrix_test

class NBFeatures(BaseEstimator):
    """Naive Bayes Feature Class

    Args:
        BaseEstimator (class): Base estimator class from Scikit-learn
    """

    def __init__(self, alpha):
        """
        Initialization function that sets the smoothing parameter.

        Args:
            alpha (float): Smoothing parameter used in probability estimation, typically set to 1
        """
        self.alpha = alpha

    def adjust_features(self, x, r):
        """
        Adjust the feature matrix `x` using the log probability ratio `r`.

        Args:
            x (sparse matrix): Original feature matrix
            r (sparse matrix): Log-ratio matrix obtained from the fit method

        Returns:
            sparse matrix: Adjusted feature matrix
        """
        return x.multiply(r)

    def compute_class_prob(self, x, y_i, y):
        """
        Compute the conditional probability for a given class `y_i`.

        Args:
            x (sparse matrix): Feature data
            y_i (int): Target class label
            y (array): Full array of labels for the dataset

        Returns:
            sparse matrix: Conditional probability for the specified class
        """
        y = np.array(y)
        mask = (y == y_i)
        p = x[mask].sum(0)

        return (p + self.alpha) / (mask.sum() + self.alpha)

    def fit(self, x, y=None):
        """
        Compute the log probability ratio for each feature and store it as a sparse matrix.

        Args:
            x (sparse matrix): Feature data
            y (array, optional): Label array for the dataset

        Returns:
            self: Returns the instance itself to allow method chaining
        """
        self._r = sparse.csr_matrix(np.log(self.compute_class_prob(
            x, 1, y) / self.compute_class_prob(x, 0, y)))
        return self

    def transform(self, x):
        """
        Apply the Naive Bayes transformation to the original feature matrix `x`.

        Args:
            x (sparse matrix): Original feature matrix

        Returns:
            sparse matrix: Transformed feature matrix
        """
        x_nb = self.adjust_features(x, self._r)
        return x_nb


def get_coefs(word, *arr):
    """
    Convert a word and its associated vector values from a GloVe file into a more usable format.

    Args:
        word (str): The word read from the GloVe file.
        *arr (str): Vector values associated with the word, passed in as strings and converted to a NumPy float32 array.

    Returns:
        tuple: A tuple containing the word and its corresponding vector as a NumPy array. 
               If conversion fails, returns the word and None.
    """
    try:
        return word, np.asarray(arr, dtype='float32')
    except ValueError:
        return word, None


def Bert_preprocess(input_text, tokenizer):
    """
    Preprocess input text using the specified tokenizer for BERT-based models.

    Args:
        input_text (str): Raw input text string to be processed.
        tokenizer: Tokenizer object used for processing the text.

    Returns:
        dict: A dictionary containing the encoded input data, including input IDs,
              attention masks, etc., formatted as PyTorch tensors.
    """
    return tokenizer.encode_plus(
        input_text,
        add_special_tokens=True,
        padding="max_length",
        max_length=512,
        truncation=True,
        return_attention_mask=True,
        return_tensors='pt'
    )


def Bert_compute_batch_accuracy(logits, labels):
    """
    Compute the accuracy for a batch of data.

    Args:
        logits (numpy.ndarray): Model output scores, typically the raw prediction values for each class.
        labels (numpy.ndarray): Ground truth labels, usually in one-hot encoded format.

    Returns:
        float: The computed accuracy score.
    """
    preds = np.argmax(logits, axis=1).flatten()
    truth = np.argmax(labels, axis=1).flatten()
    return accuracy_score(truth, preds)
