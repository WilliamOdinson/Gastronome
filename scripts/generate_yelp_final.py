import pandas as pd
import numpy as np
import re

business_df = pd.read_json('../database/yelp_academic_dataset_business.json', lines=True)
review_df = pd.read_json('../database/yelp_academic_dataset_review.json', lines=True)
pred_df = pd.read_json('../database/review_predictions.json', lines=True)

_lambda = 0.3
review_df = review_df.merge(pred_df, on='review_id', how='left')
review_df['stars'] = (_lambda * review_df['predicted_stars']
                      + (1 - _lambda) * review_df['true_stars']).round(2)
review_df.drop(['predicted_stars'], axis=1, inplace=True)

CATEGORY_KEYWORDS = {
    "Restaurants": ["restaurant",
                    r"\w+an$",
                    r"\w+ese$",
                    r"\w+ish$",
                    r"\w+ch$",
                    r"\w+ic$",
                    "food"]
}

restaurants = business_df[business_df['categories'].apply(
    lambda x: any(re.search(pattern, str(x).lower())
                  for pattern in CATEGORY_KEYWORDS["Restaurants"])
)]

restaurant_reviews = review_df[review_df.business_id.isin(restaurants['business_id'])]
yelp_cleaned = restaurant_reviews.drop(['text', 'useful', 'cool', 'date', 'funny'], axis=1)

yelp_full = yelp_cleaned.merge(
    business_df[['state', 'city', 'categories', 'business_id']],
    how='inner',
    on='business_id'
)

df = yelp_full.dropna()
df.to_csv('../database/Yelp_final.csv', index=False)
