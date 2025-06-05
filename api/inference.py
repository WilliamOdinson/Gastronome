from grpc_services.clients.inference_client import predict_class as _remote


def predict_score(text: str) -> int:
    return _remote(text)
