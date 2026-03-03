"""
gRPC client for the RecommendationService.

Exposes three convenience functions consumed by Celery tasks:

- ``user_recs``      — personalised top-K for one user.
- ``state_hotlist``   — popularity-based top-K for a state.
- ``iter_matrix``     — server-streaming RPC that yields the full
  ``(user_id, business_ids[])`` prediction matrix for Redis bulk write.

The gRPC stub is created once via ``lru_cache``.
"""

import grpc
import logging
from functools import lru_cache
from typing import Generator, Tuple, List

from grpc_services import recommend_pb2, recommend_pb2_grpc

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _stub():
    logger.info("Creating gRPC channel to localhost:50051")
    channel = grpc.insecure_channel("localhost:50051")
    return recommend_pb2_grpc.RecommendationServiceStub(channel)


def user_recs(user_id: str, state: str, k: int = 40) -> List[str]:
    """
    Request top-k personalized recommendations for a single user.
    """
    logger.info("Calling user_recs for user_id=%s, state=%s, k=%d", user_id, state, k)
    req = recommend_pb2.UserRecRequest(user_id=user_id, state=state, k=k)
    resp = _stub().GetUserRecs(req)
    logger.info("Received %d recs for user_id=%s", len(resp.business_ids), user_id)
    return list(resp.business_ids)


def state_hotlist(state: str, k: int = 40) -> List[str]:
    """
    Request top-k popular businesses for a given state.
    """
    logger.info("Calling state_hotlist for state=%s, k=%d", state, k)
    req = recommend_pb2.StateRequest(state=state, k=k)
    resp = _stub().GetStateHotlist(req)
    logger.info("Received %d hot businesses for state=%s", len(resp.business_ids), state)
    return list(resp.business_ids)


def iter_matrix(state: str, k: int = 40) -> Generator[Tuple[str, List[str]], None, None]:
    """
    Stream the entire recommendation matrix for a state.
    Yields tuples of (user_id, list of business_ids).
    """
    logger.info("Calling iter_matrix for state=%s, k=%d", state, k)
    req = recommend_pb2.StateRequest(state=state, k=k)
    count = 0
    for row in _stub().PredictMatrix(req):
        yield row.user_id, list(row.business_ids)
        count += 1
        if count % 1000 == 0:
            logger.info("Streamed %d user recs for state=%s so far...", count, state)
    logger.info("Finished streaming total %d users for state=%s", count, state)
