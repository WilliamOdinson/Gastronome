import os
import logging
import logging.config
from concurrent.futures import ThreadPoolExecutor

import grpc
import numpy as np
import torch
import warnings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Gastronome.settings")
import django  # noqa
django.setup()

from django.conf import settings  # noqa
from business.models import Business  # noqa
from recommend.services import _load_ensemble, TOP_K, get_state_hotlist  # noqa
from transformers import (  # noqa
    DistilBertTokenizerFast,
    DistilBertForSequenceClassification,
    DistilBertConfig,
)

from grpc_services import (  # noqa
    inference_pb2,
    inference_pb2_grpc,
    recommend_pb2,
    recommend_pb2_grpc,
)

# Configure module-level logger
logging.config.dictConfig(settings.LOGGING)
logger = logging.getLogger("grpc_server")


def _rows_topk(mat: np.ndarray, k: int) -> np.ndarray:
    """
    Given a 2D array 'mat' of shape (num_users, num_items),
    return a (num_users, k) array where each row contains the
    indices of the top-k values from the corresponding row of mat,
    sorted by descending score.
    """
    logger.debug("Computing top-%d indices for each of %d rows", k, mat.shape[0])
    part = np.argpartition(-mat, k - 1, axis=1)[:, :k]
    scores = mat[np.arange(mat.shape[0])[:, None], part]
    order = np.argsort(-scores, axis=1)
    result = part[np.arange(mat.shape[0])[:, None], order]
    logger.debug("Completed computing top-%d indices", k)
    return result


class ReviewScorer:
    """
    Loads a DistilBERT tokenizer and model for text classification.
    """

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
        """
        Perform inference on input text and return the predicted class index (0-5).
        """
        toks = self.tokenizer(
            text,
            max_length=512,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        toks = {k: v.to(self.device) for k, v in toks.items()}
        with torch.no_grad():
            logits = self.model(**toks).logits
            pred = int(torch.argmax(logits, dim=1).item())
        return pred


class InferenceServicer(inference_pb2_grpc.InferenceServiceServicer):
    """
    gRPC servicer for text classification.
    """

    def __init__(self):
        logger.info("Creating InferenceServicer")
        self.scorer = ReviewScorer(
            tok_path="assets/distilbert-base-uncased",
            weight_path="assets/weights/model_distilbert_cls.pth",
        )

    def PredictClass(self, request, context):
        """
        RPC method: receive InferenceRequest(text), return InferenceResponse(class_id).
        """
        pred = self.scorer(request.text)
        return inference_pb2.InferenceResponse(class_id=pred)


class CachedState:
    """
    Manage a single state's ensemble model, prediction matrix, and cached results.
    """

    def __init__(self, state: str, k: int = TOP_K):
        self.state = state.upper()
        self.k = k

        # These attributes are initialized on first use
        self.model = None
        self.user_map = None
        self.user_map_inv = None
        self.item_map = None
        self.item_map_inv = None
        self.user_topk = None
        self.hotlist = None

        logger.info("CachedState created for state '%s' (k=%d), not yet loaded", self.state, self.k)

    def _ensure_loaded(self):
        """
        If the model and prediction data are not loaded, perform:
          1. Load trained ensemble model.
          2. Build user_id <-> row index mappings.
          3. Build item index <-> business_id mappings.
          4. Compute full prediction matrix via model.predict_matrix().
          5. Compute top-k indices per row and map to business_ids.
          6. Compute hotlist for fallback recommendations.
        """
        if self.model is not None:
            logger.debug("CachedState for '%s' already loaded, skipping", self.state)
            return

        # Step 1: load ensemble model
        logger.info("Loading ensemble model for state '%s'", self.state)
        self.model = _load_ensemble(self.state)

        # Step 2: build user_id -> row_index, and inverse mapping
        logger.debug("Building user_id mappings")
        self.user_map = self.model.user_map
        self.user_map_inv = {idx: uid for uid, idx in self.user_map.items()}

        # Step 3: build item index -> business_id, inverse mapping
        logger.debug("Building item index mappings")
        self.item_map = self.model.item_map
        self.item_map_inv = {idx: bid for bid, idx in self.item_map.items()}

        # Step 4: compute full prediction matrix (numpy array shape: [num_users, num_items])
        logger.info("Computing full prediction matrix for state '%s'", self.state)
        preds = self.model.predict_matrix()
        logger.info("Full prediction matrix shape: %s", preds.shape)

        # Step 5: compute top-k indices per row
        idx_topk = _rows_topk(preds, self.k)

        # Build user_topk: map user_id to list of top-k business_ids
        logger.info("Building user_topk dictionary")
        self.user_topk = {}
        for row_idx, item_indices in enumerate(idx_topk):
            uid = self.user_map_inv[row_idx]
            bids = [self.item_map_inv[col_idx] for col_idx in item_indices]
            self.user_topk[uid] = bids

        # Step 6: compute hotlist for fallback recommendations
        logger.info("Computing hotlist for state '%s'", self.state)
        self.hotlist = get_state_hotlist(self.state, self.k)
        logger.info("Hotlist for state '%s' loaded from database", self.state)

        logger.info("Finished loading '%s': %d users cached, hotlist ready",
                    self.state, len(self.user_topk))

    def get_user_recs(self, user_id: str, k: int):
        """
        Return the top-k business_ids for a given user_id.
        If user_id is not in the training model (cold start), return None.
        """
        logger.debug("get_user_recs called for user_id '%s', k=%d", user_id, k)
        self._ensure_loaded()
        if user_id not in self.user_topk:
            logger.debug("User '%s' not found in model for state '%s'", user_id, self.state)
            return None
        result = self.user_topk[user_id][:k]
        logger.debug("Returning %d recommendations for user '%s'", len(result), user_id)
        return result

    def get_hotlist(self, k: int):
        """
        Return the top-k popular business_ids for this state.
        """
        logger.debug("get_hotlist called for state '%s', k=%d", self.state, k)
        self._ensure_loaded()
        result = self.hotlist[:k]
        logger.debug("Returning hotlist of length %d for state '%s'", len(result), self.state)
        return result

    def iter_matrix(self, k: int):
        """
        Stream (user_id, top-k business_ids) for all users in this state.
        Used by Celery to batch write into Redis.
        """
        logger.info("iter_matrix called for state '%s', k=%d", self.state, k)
        self._ensure_loaded()
        for uid, bids in self.user_topk.items():
            logger.debug("Yielding top-%d list for user '%s'", k, uid)
            yield uid, bids[:k]


class RecommendationServicer(recommend_pb2_grpc.RecommendationServiceServicer):
    """
    gRPC servicer for recommendation endpoints:
    """

    def __init__(self, states: list[str], k: int = TOP_K):
        logger.info("Initializing RecommendationServicer with states: %s", states)
        # Initialize CachedState for each state without loading model
        self.cached: dict[str, CachedState] = {
            st.upper(): CachedState(st, k) for st in states
        }
        self.k = k

    def GetUserRecs(self, request, context):
        """
        RPC method: receive UserRecRequest(user_id, state, k), return RecListResponse.
        If user_id not in model, fallback to hotlist.
        """
        logger.info("Received GetUserRecs request: user_id='%s', state='%s', k=%d",
                    request.user_id, request.state, request.k)
        st = request.state.upper()
        cache = self.cached.get(st)
        if cache is None:
            logger.error("State '%s' not loaded", st)
            context.abort(grpc.StatusCode.NOT_FOUND, f"state {st} not loaded")
        bids = cache.get_user_recs(request.user_id, request.k)
        if bids is None:
            logger.info("User '%s' cold start, returning hotlist", request.user_id)
            bids = cache.get_hotlist(request.k)
        logger.info("Returning %d recommendations to user '%s'", len(bids), request.user_id)
        return recommend_pb2.RecListResponse(business_ids=bids)

    def GetStateHotlist(self, request, context):
        """
        RPC method: receive StateRequest(state, k), return RecListResponse of hotlist.
        """
        logger.info("Received GetStateHotlist request: state='%s', k=%d", request.state, request.k)
        st = request.state.upper()
        cache = self.cached.get(st)
        if cache is None:
            logger.error("State '%s' not loaded", st)
            context.abort(grpc.StatusCode.NOT_FOUND, f"state {st} not loaded")
        hotlist = cache.get_hotlist(request.k)
        logger.info("Returning hotlist of length %d for state '%s'", len(hotlist), st)
        return recommend_pb2.RecListResponse(business_ids=hotlist)

    def PredictMatrix(self, request, context):
        """
        RPC method: receive StateRequest(state, k), stream RecRow(user_id, business_ids).
        Celery will iterate over this to write into Redis.
        """
        logger.info("Received PredictMatrix request: state='%s', k=%d", request.state, request.k)
        st = request.state.upper()
        cache = self.cached.get(st)
        if cache is None:
            logger.error("State '%s' not loaded", st)
            context.abort(grpc.StatusCode.NOT_FOUND, f"state {st} not loaded")
        for uid, bids in cache.iter_matrix(request.k):
            logger.debug("Streaming recommendations for user '%s'", uid)
            yield recommend_pb2.RecRow(user_id=uid, business_ids=bids[:request.k])


def serve():
    states = [s.strip().upper() for s in settings.AVAILABLE_STATES]
    logger.info("States to load: %s", states)

    server = grpc.server(ThreadPoolExecutor(max_workers=16))
    inference_pb2_grpc.add_InferenceServiceServicer_to_server(InferenceServicer(), server)
    recommend_pb2_grpc.add_RecommendationServiceServicer_to_server(
        RecommendationServicer(states, TOP_K),
        server
    )
    server.add_insecure_port("[::]:50051")
    server.start()
    logger.info("gRPC server ready on :50051")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
