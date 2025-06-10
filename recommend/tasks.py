import json
import logging
from typing import Dict, List

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, OuterRef, Subquery

from business.models import Business
from review.models import Review
from recommend.services import TOP_K, USER_TIMEOUT, STATE_TIMEOUT

from grpc_services.clients.recommend_client import user_recs, state_hotlist, iter_matrix

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(queue="recommendation")
def warmup_state_hotlists() -> int:
    """
    Cache top-40 hot-lists for every state once at worker start.
    """
    logger.info("Starting warmup_state_hotlists task")
    total = 0
    for state in Business.objects.values_list("state", flat=True).distinct():
        logger.info("Fetching hotlist from gRPC for state: %s", state)
        bids = state_hotlist(state, TOP_K)
        logger.info("Received %d hot businesses for state: %s", len(bids), state)
        cache.set(f"rec:state:{state}", bids, timeout=STATE_TIMEOUT)
        logger.info("Cached hotlist for state: %s", state)
        total += 1
    logger.info("warmup_state_hotlists completed: %d states cached", total)
    return total


@shared_task(queue="recommendation")
def precache_recommendations(state: str = "PA", batch: int = 2_000) -> int:
    """
    Use gRPC prediction matrix to pull the entire state matrix at once and batch write to cache.
    """
    logger.info("Starting precache_recommendations for state=%s", state)

    logger.info("Filtering active users with >=10 reviews")
    sub = (
        Review.objects.filter(user_id=OuterRef("pk"))
        .values("user_id")
        .annotate(c=Count("*"))
        .values("c")[:1]
    )
    active: Dict[str, int] = {
        str(u.pk): u.pk
        for u in User.objects.annotate(rc=Subquery(sub)).filter(rc__gte=10)
    }
    logger.info("Found %d active users in DB for state=%s", len(active), state)

    logger.info("Calling gRPC iter_matrix to stream recs for state=%s", state)
    pipe = cache.client.get_client(write=True).pipeline()
    written = 0

    sample_keys = list(active.keys())[:5]
    logger.debug("Sample active user keys (strings of PK): %s", sample_keys)

    for uid, bids in iter_matrix(state, TOP_K):

        pk = active.get(uid)
        if not pk:
            logger.debug("No matching active PK for uid=%r, skipping", uid)
            continue

        pipe.setex(f"rec:user:{pk}", USER_TIMEOUT, json.dumps(bids))
        written += 1

        if written % batch == 0:
            pipe.execute()
            logger.info("Batch write: %d user recs cached to Redis", written)

    pipe.execute()
    logger.info("Finished user recs: total %d cached", written)

    logger.info("Fetching and caching state hotlist for state=%s", state)
    cache.set(f"rec:state:{state}", state_hotlist(state, TOP_K), timeout=STATE_TIMEOUT)
    logger.info("precache_recommendations done for state=%s", state)

    return written


@shared_task(queue="recommendation")
def compute_user_recs(user_pk: int, state: str, k: int = TOP_K) -> None:
    """
    Single-user real-time recommendation: If the cache is missed, call gRPC.
    """
    logger.info("Starting compute_user_recs for user_pk=%s, state=%s", user_pk, state)
    cache_key = f"rec:user:{user_pk}"
    if cache.get(cache_key):
        logger.info("User rec already cached for user_pk=%s", user_pk)
        return

    user = User.objects.filter(pk=user_pk).first()
    if not user:
        logger.warning("User not found for user_pk=%s", user_pk)
        return

    review_count = Review.objects.filter(user=user).count()
    if review_count < 10:
        logger.info("User %s has only %d reviews, skipping", user.user_id, review_count)
        return

    logger.info("Calling gRPC user_recs for user_id=%s", user.user_id)
    bids = user_recs(user.user_id, state, k)
    cache.set(cache_key, bids, timeout=USER_TIMEOUT)
    logger.info("compute_user_recs: cached %d recs for user_pk=%s", len(bids), user_pk)
