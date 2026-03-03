"""
Recommendation service layer.

Centralises all recommendation logic consumed by views and Celery tasks:

- **FAISS KNN** — ``get_similar_businesses`` performs approximate nearest-
  neighbour search over node2vec business embeddings stored in a
  memory-mapped matrix, returning same-state results.
- **Ensemble model** — ``get_user_recommendations`` loads the per-state
  ALS+SGD+SVD ensemble pickle and returns personalised top-K business IDs.
- **State hot-list** — ``get_state_hotlist`` returns high-rated, highly-
  reviewed businesses as a fallback for cold-start users.
- **Click logging** — ``log_click`` records page-view events and
  maintains a Redis counter for trending detection.
- **Fetch orchestrator** — ``fetch_recommendations`` decides between
  personalised and state-level recommendations, dispatching an async
  Celery task if the user's cache is cold.
"""

import json
import logging
import random
import threading
from pathlib import Path
from typing import Dict, List

import faiss
import numpy as np
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from importlib import import_module

from business.models import Business
from review.models import Review
from recommend.models import Click

# constants
TOP_K: int = 40
RETURN_N: int = 8
USER_TIMEOUT: int = 3600
STATE_TIMEOUT: int = 86400
CLICK_TIMEOUT: int = 3600

logger = logging.getLogger(__name__)
_MODELS: Dict[str, object] = {}

# global caches
_INDEX = None
_IDS: np.ndarray | None = None
_STR2INT: Dict[str, int] | None = None
_VEC_MM: np.memmap | None = None
_LOCK = threading.Lock()

ROOT = Path(settings.BASE_DIR)
WEIGHTS_DIR = ROOT / "assets" / "weights"
INDEX_PATH = WEIGHTS_DIR / "biz_hnsw.index"
MAP_PATH = WEIGHTS_DIR / "biz_id.npy"
MM_PATH = WEIGHTS_DIR / "biz_emb.f32"


def _load_knn_index():
    """
    Thread-safe lazy loading of the FAISS index and embedding matrix.
    """
    global _INDEX, _IDS, _STR2INT, _VEC_MM
    if _INDEX is None:
        with _LOCK:
            if _INDEX is None:
                # 1. index + id map
                _INDEX = faiss.read_index(str(INDEX_PATH))
                _IDS = np.load(str(MAP_PATH), allow_pickle=True)
                _STR2INT = {s: i for i, s in enumerate(_IDS)}
                faiss.omp_set_num_threads(4)

                # 2. memory-mapped vectors
                rows, dims = _INDEX.ntotal, _INDEX.d
                _VEC_MM = np.memmap(MM_PATH, dtype="float32", mode="r", shape=(rows, dims))

                logger.info("FAISS index loaded: %d vectors × %d dims, mem-map ready", rows, dims)
    return _INDEX, _IDS, _STR2INT, _VEC_MM


def get_similar_businesses(anchor_id: str, k: int = TOP_K, same_state: bool = True) -> List[str]:
    """
    Return <= k business_ids most similar to anchor_id
    (cosine distance on node2vec embeddings).
    Results are restricted to the same US state if same_state is True.
    """
    index, ids_arr, str2int, vec_mm = _load_knn_index()
    if anchor_id not in str2int:
        return []
    int_id = str2int[anchor_id]
    vec = np.asarray(vec_mm[int_id])
    _, ind = index.search(vec[None, :], k + 1)
    cand = [ids_arr[j] for j in ind[0] if ids_arr[j] != anchor_id]

    if same_state:
        anchor_state = (
            Business.objects.filter(business_id=anchor_id)
            .values_list("state", flat=True)
            .first()
        )
        if anchor_state:
            states = (
                Business.objects.filter(business_id__in=cand)
                .values_list("business_id", "state")
            )
            state_map = {bid: st for bid, st in states}
            cand = [bid for bid in cand if state_map.get(bid) == anchor_state]

    return cand[:k]


def log_click(request, business: Business) -> None:
    """
    Store one page-view event, either by user or session.
    Cache key: biz:clickcnt:<biz_id>
    """
    try:
        if request.user.is_authenticated:
            Click.objects.create(user=request.user, business=business)
        else:
            if not request.session.session_key:
                request.session.create()
            Click.objects.create(
                session_key=request.session.session_key,
                business=business,
            )

        cache_key = f"biz:clickcnt:{business.business_id}"

        # create the key with TTL = 24 h if it does not exist
        cache.add(cache_key, 0, timeout=86400)
        # now we can increment safely
        cache.incr(cache_key)

    except Exception:
        logger.exception("log_click failed")


def get_click_recommendations(business_id: str, n: int = RETURN_N) -> List[Business]:
    """
    Retrieve n similar businesses for the detail page.
    Falls back to the same-state hot list if fewer than n neighbors are available.
    Cache key: rec:click:<biz_id>
    """
    cache_key = f"rec:click:{business_id}"
    raw = cache.get(cache_key)
    try:
        ids = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except Exception:
        ids = []

    if not ids:
        ids = get_similar_businesses(business_id, k=TOP_K, same_state=True)
        cache.set(cache_key, json.dumps(ids), timeout=CLICK_TIMEOUT)

    if len(ids) < n:
        anchor_state = (
            Business.objects.filter(business_id=business_id)
            .values_list("state", flat=True)
            .first()
            or "PA"
        )
        hot = get_state_hotlist(anchor_state, TOP_K)
        ids.extend(b for b in hot if b not in ids)
    trimmed = _sample_keep_order(ids, n)
    return Business.objects.filter(business_id__in=trimmed)


def _load_ensemble(state: str = "PA"):
    """
    Lazy load the per-state ensemble recommender pickle.
    """
    state = state.lower()
    if state not in _MODELS:
        mod = import_module("recommend.algorithm.ensemble_recommender")
        path = WEIGHTS_DIR / f"ensemble_{state}.pkl"
        _MODELS[state] = mod.EnsembleRecommender.load(path)
    return _MODELS[state]


def _sample_keep_order(seq: List[str], k: int) -> List[str]:
    """
    Randomly sample k elements while preserving the original order in seq.
    """
    if len(seq) <= k:
        return seq
    idx = sorted(random.sample(range(len(seq)), k))
    return [seq[i] for i in idx]


def get_user_recommendations(user, state: str, k: int = TOP_K) -> List[str]:
    """
    Personalized top-K business ids predicted by the ensemble model for a given user.
    """
    model = _load_ensemble(state)
    pairs = model.predict(user.user_id, n=k)
    return [bid for bid, _ in pairs]


def get_state_hotlist(state: str = "PA", k: int = TOP_K) -> List[str]:
    """
    Return k high-quality businesses within a state based on star rating and review count.
    """
    cache_key = f"hotlist:{state}:{k}"
    hotlist = cache.get(cache_key)

    if not hotlist:
        logger.info(f"Cache miss for {state} hotlist, fetching from DB...")
        qs = (
            Business.objects.filter(state=state)
            .filter(stars__gte=4.0, review_count__gte=400)
            .annotate(rc=Count("reviews"))
            .order_by("-stars", "-rc")[:64]
        )
        ids = list(qs.values_list("business_id", flat=True))
        random.shuffle(ids)
        hotlist = ids[:k]

        # Set cache with a timeout of 12 hours
        cache.set(cache_key, hotlist, timeout=43200)
    else:
        logger.info(f"Cache hit for {state} hotlist")

    return hotlist


def fetch_recommendations(user, state: str = "PA", n: int = RETURN_N):
    """
    Fetch n business recommendations for a user or state.
    If the user is authenticated and has at least 10 reviews, compute personalized recommendations.
    Otherwise, return a state-based hot list.
    """
    state = state.upper()

    eligible = (
        user.is_authenticated
        and Review.objects.filter(user=user).count() >= 10
    )

    if eligible:
        cache_key = f"rec:user:{user.pk}"
        timeout = USER_TIMEOUT
    else:
        cache_key = f"rec:state:{state}"
        timeout = STATE_TIMEOUT

    raw = cache.get(cache_key)
    try:
        ids = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except Exception:
        ids = []

    if eligible and not ids:
        # async compute; return fallback now
        from recommend.tasks import compute_user_recs
        logger.info("dispatching compute_user_recs for user=%s", user.pk)
        compute_user_recs.delay(user.pk, state)
        ids = cache.get(f"rec:state:{state}") or get_state_hotlist(state, TOP_K)
        # ensure fallback hot-list is cached (idempotent)
        cache.set(f"rec:state:{state}", ids, timeout=STATE_TIMEOUT)

    # still no ids: take hot-list (cold-start)
    if not ids:
        if eligible:
            from recommend.tasks import compute_user_recs
            compute_user_recs.delay(user.pk, state)
            ids = get_state_hotlist(state, TOP_K)
            cache_key = f"rec:state:{state}"
            timeout = STATE_TIMEOUT
            cache.set(cache_key, json.dumps(ids), timeout=timeout)

    trimmed = _sample_keep_order(ids, n)
    return Business.objects.filter(business_id__in=trimmed)
