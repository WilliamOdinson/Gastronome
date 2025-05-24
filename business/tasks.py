import logging
from itertools import islice
from time import perf_counter
from typing import Iterable, List

from celery import group, shared_task
from django.db import transaction
from django.utils import timezone

from business.models import Business

logger = logging.getLogger(__name__)


BATCH_SIZE = 3000


def _batched(iterable: Iterable[str], n: int) -> Iterable[List[str]]:
    """Yield successive n-sized chunks from an iterable."""
    it = iter(iterable)
    while True:
        batch = list(islice(it, n))
        if not batch:
            break
        yield batch


@shared_task(queue="business_status")
def refresh_open_batch(id_batch: List[str]) -> int:
    """
    Update a batch of businesses' is_open status.
    """
    now = timezone.now()
    start_ts = perf_counter()

    queryset = (
        Business.objects.filter(pk__in=id_batch)
        .only("business_id", "is_open", "latitude", "longitude", "timezone")
        .iterator(chunk_size=512)
    )

    updates: List[Business] = []
    for business in queryset:
        open_now = business.calculate_open_status(now)
        if open_now != business.is_open:
            business.is_open = open_now
            updates.append(business)

    changed = len(updates)
    if changed:
        with transaction.atomic():
            Business.objects.bulk_update(
                updates,
                ["is_open"],
                batch_size=1000
            )

    elapsed = perf_counter() - start_ts
    logger.info(
        "refresh_open_batch processed %d rows, updated %d, elapsed %.2f s",
        len(id_batch),
        changed,
        elapsed
    )

    return changed


@shared_task(queue="business_status")
def refresh_open_status() -> None:
    """
    Dispatch the full is_open update job in parallel batches.
    Does not wait for completion to avoid blocking the beat scheduler.
    """
    ids = list(Business.objects.values_list("business_id", flat=True))
    batches = list(_batched(ids, BATCH_SIZE))

    job = group(
        refresh_open_batch.s(batch).set(queue="business_status")
        for batch in batches
    )
    result = job.apply_async(queue="business_status")

    logger.info(
        "refresh_open_status dispatched %d batches, group_id=%s",
        len(batches),
        result.id
    )
