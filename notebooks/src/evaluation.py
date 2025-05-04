import pandas as pd


def build_ensemble_dataframe(svd_predictions, cosine_predictions, als_predictions, sgd_predictions, rf_predictions):
    """
    Build DataFrame containing predictions from multiple models.

    Args:
        svd_predictions (numpy.ndarray): Predictions from SVD model
        cosine_predictions (numpy.ndarray): Predictions from cosine similarity model
        als_predictions (numpy.ndarray): Predictions from ALS model
        sgd_predictions (numpy.ndarray): Predictions from SGD model
        rf_predictions (numpy.ndarray): Predictions from Random Forest model

    Returns:
        pandas.DataFrame: DataFrame with all model predictions
    """
    ensemble_df = pd.DataFrame(svd_predictions, columns=['SVD'])
    ensemble_df['Cosine'] = cosine_predictions
    ensemble_df['ALS'] = als_predictions
    ensemble_df['SGD'] = sgd_predictions
    ensemble_df['Random Forest'] = rf_predictions
    
    return ensemble_df

def get_dataframe_dtypes(dataframe):
    """
    Retrieve data type information for each DataFrame column.

    Args:
        df (pandas.DataFrame): DataFrame to inspect

    Returns:
        dict: Mapping of column names to their data type as string
    """
    dtype_info = {column: str(dtype) for column, dtype in zip(dataframe.columns, dataframe.dtypes)}
    
    return dtype_info
