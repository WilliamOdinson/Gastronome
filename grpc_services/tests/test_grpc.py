import grpc
import numpy as np
import pytest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from grpc_services import (
    inference_pb2,
    inference_pb2_grpc,
    recommend_pb2,
    recommend_pb2_grpc,
)
from grpc_services.server import (
    InferenceServicer,
    RecommendationServicer,
    TOP_K,
)


class _DummyScorer:
    def __call__(self, text: str) -> int:
        return len(text) % 6


class _DummyRecModel:
    """
    Construct a 2x50 prediction matrix, enough to cover TOP_K=40.
    u1: b1(0.9) > b3(0.8) > b2(0.7)
    u2: b3(0.85) > b2(0.8) > b1(0.1)
    All other scores are zero.
    """

    def __init__(self):
        self.user_map = {"u1": 0, "u2": 1}
        self.item_map = {f"b{i}": i - 1 for i in range(1, 51)}  # b1...b50

    def predict_matrix(self) -> np.ndarray:
        mat = np.zeros((2, 50), dtype=float)
        mat[0, 0], mat[0, 2], mat[0, 1] = 0.9, 0.8, 0.7
        mat[1, 2], mat[1, 1], mat[1, 0] = 0.85, 0.8, 0.1
        return mat


def _dummy_hotlist(state: str, k: int):
    return [f"b{i}" for i in range(1, k + 1)]


@pytest.fixture(scope="session")
def grpc_addr():
    """
    Start a real gRPC server in an independent thread pool, but Monkey-Patch all
    costly dependencies with local stub objects.
    """
    with (
        mock.patch("grpc_services.server.ReviewScorer", lambda *_, **__: _DummyScorer()),
        mock.patch("grpc_services.server._load_ensemble", lambda *_: _DummyRecModel()),
        mock.patch("grpc_services.server.get_state_hotlist", _dummy_hotlist),
    ):
        server = grpc.server(ThreadPoolExecutor(max_workers=8))
        inference_pb2_grpc.add_InferenceServiceServicer_to_server(
            InferenceServicer(), server
        )
        recommend_pb2_grpc.add_RecommendationServiceServicer_to_server(
            RecommendationServicer(states=["AZ"], k=TOP_K), server
        )
        port = server.add_insecure_port("localhost:0")
        server.start()
        yield f"localhost:{port}"
        server.stop(0)


def test_predict_class_returns_modulo(grpc_addr):
    """
    Test that the PredictClass method returns the correct class ID based on
    the length of the input text modulo 6.
    """
    channel = grpc.insecure_channel(grpc_addr)
    stub = inference_pb2_grpc.InferenceServiceStub(channel)

    text = "delicious burger"
    resp = stub.PredictClass(inference_pb2.InferenceRequest(text=text))

    assert resp.class_id == 4


def test_user_recs_hit_model(grpc_addr):
    """
    Test that the GetUserRecs method returns the top-k recommendations for a user
    based on the dummy recommendation model.
    """
    channel = grpc.insecure_channel(grpc_addr)
    stub = recommend_pb2_grpc.RecommendationServiceStub(channel)

    resp = stub.GetUserRecs(
        recommend_pb2.UserRecRequest(user_id="u1", state="AZ", k=3)
    )

    assert resp.business_ids == ["b1", "b3", "b2"]


def test_user_recs_cold_start_falls_back_to_hotlist(grpc_addr):
    """
    Test that the GetUserRecs method falls back to the state hotlist for a user
    with no prior interactions.
    """
    channel = grpc.insecure_channel(grpc_addr)
    stub = recommend_pb2_grpc.RecommendationServiceStub(channel)

    resp = stub.GetUserRecs(
        recommend_pb2.UserRecRequest(user_id="u999", state="AZ", k=2)
    )

    assert resp.business_ids == ["b1", "b2"]


def test_state_hotlist(grpc_addr):
    """
    Test that the GetStateHotlist method returns the top-k hot businesses for a state.
    """
    channel = grpc.insecure_channel(grpc_addr)
    stub = recommend_pb2_grpc.RecommendationServiceStub(channel)

    resp = stub.GetStateHotlist(recommend_pb2.StateRequest(state="az", k=4))

    assert resp.business_ids == ["b1", "b2", "b3", "b4"]


def test_predict_matrix_streaming(grpc_addr):
    """
    Test that the PredictMatrix method returns a stream of user IDs and their
    top-k business recommendations.
    """
    channel = grpc.insecure_channel(grpc_addr)
    stub = recommend_pb2_grpc.RecommendationServiceStub(channel)

    rows = list(
        stub.PredictMatrix(recommend_pb2.StateRequest(state="AZ", k=2))
    )

    assert [(r.user_id, r.business_ids) for r in rows] == [
        ("u1", ["b1", "b3"]),
        ("u2", ["b3", "b2"]),
    ]
