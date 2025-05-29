import torch
import warnings
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification, DistilBertConfig


class ReviewScorer:
    def __init__(self, tokenizer_path: str, model_weights_path: str):
        self.tokenizer = DistilBertTokenizerFast.from_pretrained(tokenizer_path, do_lower_case=True)

        config = DistilBertConfig.from_pretrained(tokenizer_path)
        config.num_labels = 6
        config.output_attentions = False
        config.output_hidden_states = False

        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            self.model = DistilBertForSequenceClassification(config)

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        state_dict = torch.load(model_weights_path, map_location=device)
        self.model.load_state_dict(state_dict)
        self.model.eval()
        self.model.to(device)
        self.device = device

    def predict(self, text: str) -> int:
        inputs = self.tokenizer(
            text,
            max_length=512,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            logits = self.model(**inputs).logits
            pred_class = torch.argmax(logits, dim=1).item()
            return int(pred_class)


scorer = ReviewScorer(
    tokenizer_path='assets/distilbert-base-uncased',
    model_weights_path='assets/weights/model_distilbert_cls.pth'
)


def predict_score(text: str) -> int:
    return scorer.predict(text)
