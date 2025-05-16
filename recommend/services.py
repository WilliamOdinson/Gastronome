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

def _load_ensemble():
    global _MODEL
    if _MODEL is None:
        module = import_module("recommend.algorithm.ensemble_recommender")
        _MODEL = module.EnsembleRecommender.load(_MODEL_PATH)
    return _MODEL

def get_user_recommendations(user, n: int = 8) -> List[str]:
    model = _load_ensemble()
    # ensemble.predict returns a list of (business_id, score) tuples
    recs = model.predict(user.user_id, n=n)
    return [bid for bid, _ in recs]

def get_state_hotlist(state: str = "PA", n: int = 8) -> List[str]:
    qs = (
        Business.objects.filter(state=state)
        .filter(stars__gte=4.0, review_count__gte=400)
        .annotate(rc=Count("reviews"))
        .order_by("-stars", "-rc")[:64]  # Fetch top 64 candidates to diversify randomness
    )
    ids = list(qs.values_list("business_id", flat=True))
    random.shuffle(ids)
    return ids[:n]

def fetch_recommendations(user, state: str = "PA", n: int = 8):
    """
    Check Redis cache first; if not found, compute and store it.
    If the user is logged in and has at least 10 reviews, use personalized recommendations.
    Otherwise, fall back to popular businesses in the given state.
    """
    if user.is_authenticated and Review.objects.filter(user=user).count() >= 10:
        cache_key = f"rec:user:{user.pk}"
        timeout = 3600  # 1 hour
        loader = lambda: get_user_recommendations(user, n)
    else:
        cache_key = f"rec:state:{state}"
        timeout = 86400  # 24 hours
        loader = lambda: get_state_hotlist(state, n)

    ids = cache.get(cache_key)
    if ids is None:
        ids = loader()
        cache.set(cache_key, ids, timeout=timeout)

    return Business.objects.filter(business_id__in=ids)
