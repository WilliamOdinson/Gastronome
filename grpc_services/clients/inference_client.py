import grpc
from functools import lru_cache
from grpc_services import inference_pb2, inference_pb2_grpc


@lru_cache(maxsize=1)
def _stub():
    channel = grpc.insecure_channel("localhost:50051")
    return inference_pb2_grpc.InferenceServiceStub(channel)


def predict_class(text: str) -> int:
    resp = _stub().PredictClass(inference_pb2.InferenceRequest(text=text))
    return resp.class_id
