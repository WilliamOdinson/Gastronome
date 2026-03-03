"""
Celery tasks for bulk-updating business documents in OpenSearch.

Contains a single shared task ``push_is_open_bulk`` that performs a
partial ``_update`` on the ``is_open`` field for a batch of businesses,
avoiding a full document reindex.
"""

from typing import List

from celery import shared_task
from django.conf import settings
from opensearchpy import helpers

from business.models import Business
from Gastronome.opensearch import get_opensearch_client


@shared_task(queue="business_status")
def push_is_open_bulk(id_list: List[str]) -> int:
    """
    Pushes the 'is_open' field for a batch of businesses to OpenSearch using a bulk update.
    Only updates the document with {"is_open": ...} to avoid rewriting the entire document.
    """
    if not id_list:
        return 0

    op = get_opensearch_client()
    index = settings.OPENSEARCH["BUSINESS_INDEX"]

    qs = Business.objects.filter(pk__in=id_list).only("business_id", "is_open")

    actions = (
        {
            "_op_type": "update",
            "_index": index,
            "_id": b.business_id,
            "doc": {"is_open": b.is_open},
        }
        for b in qs
    )
    helpers.bulk(op, actions, chunk_size=1000, request_timeout=30)
    return len(id_list)
