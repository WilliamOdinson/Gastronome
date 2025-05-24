import random
from pathlib import Path
from typing import List

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from importlib import import_module

from business.models import Business
from review.models import Review

_MODEL = None
_MODEL_PATH = Path(settings.BASE_DIR) / "assets" / "weights" / "ensemble_pa.pkl"

TOP_K = 40
RETURN_N = 8


def _load_ensemble():
    global _MODEL
    if _MODEL is None:
        module = import_module("recommend.algorithm.ensemble_recommender")
        _MODEL = module.EnsembleRecommender.load(_MODEL_PATH)
    return _MODEL


def _sample_keep_order(seq: List[str], k: int) -> List[str]:
    """Randomly pick k elements but retain their original order."""
    if len(seq) <= k:
        return seq
    idx = sorted(random.sample(range(len(seq)), k))
    return [seq[i] for i in idx]


def get_user_recommendations(user, k: int = TOP_K) -> List[str]:
    """Return top-k personal business_ids."""
    model = _load_ensemble()
    pairs = model.predict(user.user_id, n=k)
    return [bid for bid, _ in pairs]


def get_state_hotlist(state: str = "PA", k: int = TOP_K) -> List[str]:
    """Return state-level hot list (randomized order)."""
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
    Return Business queryset of length n (default 8).
    Combines cache + cold-start fallback + order-preserving random cut.
    """
    if user.is_authenticated and Review.objects.filter(user=user).count() >= 10:
        cache_key = f"rec:user:{user.pk}"
        timeout = 3600
        def loader(): return get_user_recommendations(user, TOP_K)
    else:
        cache_key = f"rec:state:{state}"
        timeout = 86400
        def loader(): return get_state_hotlist(state, TOP_K)

    ids = cache.get(cache_key)
    if ids is None:
        ids = loader()
        if not ids and cache_key.startswith("rec:user:"):
            ids = get_state_hotlist(state, TOP_K)
            cache_key = f"rec:state:{state}"
            timeout = 86400
        cache.set(cache_key, ids, timeout=timeout)

    trimmed = _sample_keep_order(ids, n)
    return Business.objects.filter(business_id__in=trimmed)
