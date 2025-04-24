import numpy as np
from sklearn.base import BaseEstimator
from scipy import sparse
from scipy.sparse import csr_matrix
from sklearn.metrics import accuracy_score


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
