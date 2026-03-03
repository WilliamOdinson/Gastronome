"""
Thin inference facade.

Delegates review text → star-rating prediction to the gRPC
InferenceService running the DistilBERT classification model.
This indirection keeps the Django process free of heavy ML dependencies.
"""

from grpc_services.clients.inference_client import predict_class as _remote


def predict_score(text: str) -> int:
    """Return the predicted star class (0–5) for a review text string."""
    return _remote(text)
