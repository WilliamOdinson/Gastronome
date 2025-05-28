import torch
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification, DistilBertConfig
import pandas as pd
from tqdm import tqdm
import json

MODEL_STATE_PATH = '../assets/weights/model_distilbert_cls.pth'
TOKENIZER_PATH = '../assets/distilbert-base-uncased'
REVIEW_JSON_PATH = '../database/yelp_academic_dataset_review.json'
OUTPUT_JSON_PATH = 'review_predictions.json'

tokenizer = DistilBertTokenizerFast.from_pretrained(TOKENIZER_PATH, do_lower_case=True)

config = DistilBertConfig.from_pretrained(TOKENIZER_PATH)
config.num_labels = 6
model = DistilBertForSequenceClassification(config)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
state_dict = torch.load(MODEL_STATE_PATH, map_location=device)
model.load_state_dict(state_dict)
model.eval()
model.to(device)

columns = ['review_id', 'text', 'stars']

with open(REVIEW_JSON_PATH, 'r') as infile, open(OUTPUT_JSON_PATH, 'w') as outfile:
    for chunk in pd.read_json(infile, lines=True, chunksize=10000):
        chunk = chunk[columns]

        for _, row in tqdm(chunk.iterrows(), total=len(chunk), desc='Predicting'):
            text = row['text']
            review_id = row['review_id']
            true_rating = row['stars']

            inputs = tokenizer(
                text,
                max_length=512,
                padding='max_length',
                truncation=True,
                return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                logits = model(**inputs).logits
                predicted_class = torch.argmax(logits, dim=1).item()
                predicted_stars = predicted_class

            result = {
                'review_id': review_id,
                'predicted_stars': predicted_stars,
                'true_stars': true_rating
            }

            outfile.write(json.dumps(result) + '\n')
