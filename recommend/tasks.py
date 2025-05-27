import json
import logging
from typing import Dict, List

import numpy as np
from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, OuterRef, Subquery

from business.models import Business
from review.models import Review
from recommend.services import (
    _load_ensemble,
    get_state_hotlist,
    TOP_K,
    USER_TIMEOUT,
    STATE_TIMEOUT,
)

logger = logging.getLogger(__name__)
User = get_user_model()


def _rows_topk(mat: np.ndarray, k: int) -> List[np.ndarray]:
    """Return, for every row, the indices of its top-k scores (descending)."""
    part = np.argpartition(-mat, k - 1, axis=1)[:, :k]
    scores = mat[np.arange(mat.shape[0])[:, None], part]
    order = np.argsort(-scores, axis=1)
    return [part[i, order[i]] for i in range(mat.shape[0])]


@shared_task(queue="recommendation")
def warmup_state_hotlists() -> int:
    """Cache top-40 hot-lists for every state once at worker start."""
    total = 0
    for state in Business.objects.values_list("state", flat=True).distinct():
        bids = get_state_hotlist(state, TOP_K)
        cache.set(f"rec:state:{state}", bids, timeout=STATE_TIMEOUT)
        total += 1
    logger.info("warmup_state_hotlists cached %d states", total)
    return total


@shared_task(queue="recommendation")
def precache_recommendations(batch: int = 2_000) -> int:
    """
    Load ensemble_PA.pkl once, dump top-40 personal recs for every user present
    in the model and with >=10 reviews.  Also refresh state hot-lists.
    """
    model = _load_ensemble("PA")
    full_pred = model.predict_matrix()

    # map matrix row to Django user.pk
    idx_to_pk: Dict[int, int] = {}
    for d_user in User.objects.values("pk", "user_id"):
        if d_user["user_id"] in model.user_map:
            idx_to_pk[model.user_map[d_user["user_id"]]] = d_user["pk"]

    # only active users (>=10 reviews)
    sub = (
        Review.objects.filter(user_id=OuterRef("pk"))
        .values("user_id")
        .annotate(c=Count("*"))
        .values("c")[:1]
    )
    active = {
        u.pk for u in User.objects.annotate(rc=Subquery(sub)).filter(rc__gte=10)
    }

    topk_idx = _rows_topk(full_pred, TOP_K)

    pipe = cache.client.get_client(write=True).pipeline()
    written = 0
    for row, item_idx in enumerate(topk_idx):
        pk = idx_to_pk.get(row)
        if pk is None or pk not in active:
            continue
        bids = [model.item_map_inv[int(j)] for j in item_idx]
        pipe.setex(f"rec:user:{pk}", USER_TIMEOUT, json.dumps(bids))
        written += 1
        if written % batch == 0:
            pipe.execute()
    pipe.execute()

    # refresh state hot-lists as well
    states = Business.objects.values_list("state", flat=True).distinct()
    for st in states:
        cache.set(
            f"rec:state:{st}",
            get_state_hotlist(st, TOP_K),
            timeout=STATE_TIMEOUT,
        )
        written += 1

    logger.info("precache_recommendations wrote %d keys", written)
    return written


@shared_task(queue="recommendation")
def compute_user_recs(user_pk: int, state: str, k: int = TOP_K) -> None:
    """
    Compute personal recs for a single user asynchronously and write to cache.
    No action if user <10 reviews or we already cached.
    """
    cache_key = f"rec:user:{user_pk}"
    if cache.get(cache_key):
        return

    user = User.objects.filter(pk=user_pk).first()
    if not user:
        return
    if Review.objects.filter(user=user).count() < 10:
        return

    model = _load_ensemble(state)
    if user.user_id not in model.user_map:
        cache.set(cache_key, json.dumps(get_state_hotlist(state, TOP_K)), timeout=STATE_TIMEOUT)
        logger.info("user %s not in model - stored fallback", user_pk)
        return          # cold-start; nothing to store now

    bids = [
        bid for bid, _ in model.predict(user.user_id, n=k)
    ]
    cache.set(cache_key, bids, timeout=USER_TIMEOUT)
    logger.info("compute_user_recs cached user:%s (%d ids)", user_pk, len(bids))
