import logging
from colorama import Fore, init
from opensearchpy import NotFoundError
from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import m2m_changed, post_delete, post_save

from Gastronome.opensearch import get_opensearch_client

init(autoreset=True)
logger = logging.getLogger(__name__)


def _business_to_doc(biz) -> dict:
    """
    Convert the Business object to an OpenSearch document.
    """
    return {
        "business_id": biz.business_id,
        "name": biz.name,
        "city": biz.city,
        "state": biz.state,
        "location": {"lat": float(biz.latitude), "lon": float(biz.longitude)},
        "stars": biz.stars,
        "review_count": biz.review_count,
        "is_open": biz.is_open,
        "categories": list(biz.categories.values_list("name", flat=True)),
    }


def _sync_business_to_opensearch(sender, instance, **kwargs):
    if settings.DJANGO_TEST or settings.DATA_IMPORT:
        # print(Fore.YELLOW + f"[SKIP] OpenSearch indexing skipped")
        return

    op = get_opensearch_client()
    index = settings.OPENSEARCH["BUSINESS_INDEX"]

    if kwargs.get("signal") == post_delete:
        try:
            op.delete(index=index, id=instance.pk, ignore=[404])
        except NotFoundError:
            print(Fore.RED + f"[ERROR] Business with ID {instance.pk} not found in OpenSearch.")
        return

    # post_save or m2m_changed: Direct Upsert
    doc = _business_to_doc(instance)
    op.index(index=index, id=instance.pk, body=doc, refresh="false")


def _categories_changed(action, instance, **_):
    """
    The m2m_changed hook: Synchronization occurs only when
    there is an actual change in the tags.
    """
    if action in {"post_add", "post_remove", "post_clear"}:
        _sync_business_to_opensearch(sender=None, instance=instance)


class BusinessConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "business"

    def ready(self):
        from business.models import Business

        post_save.connect(
            _sync_business_to_opensearch,
            sender=Business,
            dispatch_uid="business_to_opensearch_save",
        )

        post_delete.connect(
            _sync_business_to_opensearch,
            sender=Business,
            dispatch_uid="business_to_opensearch_delete",
        )

        m2m_changed.connect(
            _categories_changed,
            sender=Business.categories.through,
            dispatch_uid="business_categories_opensearch_m2m",
        )
