import grpc
from concurrent.futures import ThreadPoolExecutor
import warnings
import torch
from transformers import (
    DistilBertTokenizerFast,
    DistilBertForSequenceClassification,
    DistilBertConfig,
)
from grpc_services import inference_pb2, inference_pb2_grpc


class ReviewScorer:
    def __init__(self, tok_path: str, weight_path: str):
        self.tokenizer = DistilBertTokenizerFast.from_pretrained(tok_path, do_lower_case=True)
        cfg = DistilBertConfig.from_pretrained(tok_path)
        cfg.num_labels = 6
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.model = DistilBertForSequenceClassification(cfg)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        state_dict = torch.load(weight_path, map_location=device)
        self.model.load_state_dict(state_dict)
        self.model.eval().to(device)
        self.device = device

    def __call__(self, text: str) -> int:
        toks = self.tokenizer(text, max_length=512, truncation=True,
                              padding="max_length", return_tensors="pt")
        toks = {k: v.to(self.device) for k, v in toks.items()}
        with torch.no_grad():
            logits = self.model(**toks).logits
            return int(torch.argmax(logits, dim=1).item())


class InferenceServicer(inference_pb2_grpc.InferenceServiceServicer):
    def __init__(self):
        self.scorer = ReviewScorer(
            "assets/distilbert-base-uncased",
            "assets/weights/model_distilbert_cls.pth",
        )

    def PredictClass(self, request, context):
        pred = self.scorer(request.text)
        return inference_pb2.InferenceResponse(class_id=pred)


def serve() -> None:
    server = grpc.server(ThreadPoolExecutor(max_workers=8))
    inference_pb2_grpc.add_InferenceServiceServicer_to_server(InferenceServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC Inference server ready on :50051")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
