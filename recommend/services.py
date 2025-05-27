import json
import logging
import random
from pathlib import Path
from typing import Dict, List

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from importlib import import_module

from business.models import Business
from review.models import Review

TOP_K = 40
RETURN_N = 8
USER_TIMEOUT = 3600
STATE_TIMEOUT = 86400

_MODELS: Dict[str, object] = {}


logger = logging.getLogger(__name__)


def _load_ensemble(state: str = "PA"):
    state = state.lower()
    if state not in _MODELS:
        mod = import_module("recommend.algorithm.ensemble_recommender")
        path = (
            Path(settings.BASE_DIR)
            / "assets" / "weights" / f"ensemble_{state}.pkl"
        )
        _MODELS[state] = mod.EnsembleRecommender.load(path)
    return _MODELS[state]


def _sample_keep_order(seq: List[str], k: int) -> List[str]:
    if len(seq) <= k:
        return seq
    idx = sorted(random.sample(range(len(seq)), k))
    return [seq[i] for i in idx]


def get_user_recommendations(user, state: str, k: int = TOP_K) -> List[str]:
    model = _load_ensemble(state)
    pairs = model.predict(user.user_id, n=k)
    return [bid for bid, _ in pairs]


def get_state_hotlist(state: str = "PA", k: int = TOP_K) -> List[str]:
    qs = (
        Business.objects.filter(state=state)
        .filter(stars__gte=4.0, review_count__gte=400)
        .annotate(rc=Count("reviews"))
        .order_by("-stars", "-rc")[:64]
    )
    ids = list(qs.values_list("business_id", flat=True))
    random.shuffle(ids)
    return ids[:k]


def fetch_recommendations(user, state: str = "PA", n: int = RETURN_N):
    """
    Main entry used by views.  Returns queryset of length n.
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
        if user.is_authenticated and Review.objects.filter(user=user).count() >= 10:
            # fallback + trigger celery job
            from recommend.tasks import compute_user_recs
            compute_user_recs.delay(user.pk, state)
            ids = get_state_hotlist(state, TOP_K)
            cache_key = f"rec:state:{state}"
            timeout = STATE_TIMEOUT
            cache.set(cache_key, json.dumps(ids), timeout=timeout)

    trimmed = _sample_keep_order(ids, n)
    return Business.objects.filter(business_id__in=trimmed)
