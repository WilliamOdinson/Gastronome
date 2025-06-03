import logging

from colorama import Fore, init
from opensearchpy import NotFoundError

from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_delete, post_save

from Gastronome.opensearch import get_opensearch_client


init(autoreset=True)
logger = logging.getLogger(__name__)


def _review_to_doc(r):
    """
    Convert the Review object to a document suitable for indexing in OpenSearch.
    All nullable numeric fields are defaulted to 0 to prevent mapping errors.
    """
    return {
        "review_id": r.review_id,
        "user_id": r.user_id,
        "user_name": r.user.display_name or r.user.email,
        "business_id": r.business_id,
        "business_name": r.business.name,
        "stars": r.stars,
        "date": r.date,
        "text": r.text,
        "auto_score": r.auto_score or 0.0,
        "useful": r.useful or 0,
        "funny": r.funny or 0,
        "cool": r.cool or 0,
    }


def sync_review(sender, instance, **kwargs):
    """
    Index or delete a Review document in OpenSearch when the model changes.
    Triggered on post_save and post_delete.
    """
    if getattr(settings, "DJANGO_TEST", False) or getattr(settings, "DATA_IMPORT", False):
        print(Fore.YELLOW + "[SKIP] OpenSearch indexing skipped due to test/import mode")
        return

    op = get_opensearch_client()
    idx = settings.OPENSEARCH["REVIEW_INDEX"]

    if kwargs.get("signal") == post_delete:
        try:
            op.delete(index=idx, id=instance.pk, ignore=[404], refresh="wait_for")
            print(f"Deleted review {instance.pk} from OpenSearch index {idx}")
        except NotFoundError:
            print(Fore.RED + f"[ERROR] Review {instance.pk} not found in index {idx}")
        except Exception as exc:
            print(Fore.RED + f"[ERROR] Failed to delete review {instance.pk}: {exc}")
        return

    try:
        doc = _review_to_doc(instance)
        resp = op.index(index=idx, id=instance.pk, body=doc, refresh="wait_for")
        print(f"Indexed review {instance.pk} into {idx}: result = {resp.get('result')}")
    except Exception as exc:
        print(Fore.RED + f"[ERROR] Failed to index review {instance.pk}: {exc}")


def _tip_to_doc(t):
    """
    Convert the Tip object to a document suitable for indexing in OpenSearch.
    """
    return {
        "user_id": t.user_id,
        "user_name": t.user.display_name or t.user.email,
        "business_id": t.business_id,
        "business_name": t.business.name,
        "date": t.date,
        "text": t.text,
        "compliment_count": t.compliment_count or 0,
    }


def sync_tip(sender, instance, **kwargs):
    """
    Index or delete a Tip document in OpenSearch when the model changes.
    Triggered on post_save and post_delete.
    """
    if getattr(settings, "DJANGO_TEST", False):
        print(Fore.YELLOW + "[SKIP] OpenSearch indexing skipped due to test mode")
        return

    op = get_opensearch_client()
    idx = settings.OPENSEARCH["TIP_INDEX"]

    if kwargs.get("signal") == post_delete:
        try:
            op.delete(index=idx, id=instance.pk, ignore=[404], refresh="wait_for")
            print(f"Deleted tip {instance.pk} from OpenSearch index {idx}")
        except NotFoundError:
            print(Fore.RED + f"[ERROR] Tip {instance.pk} not found in index {idx}")
        except Exception as exc:
            print(Fore.RED + f"[ERROR] Failed to delete tip {instance.pk}: {exc}")
        return

    try:
        doc = _tip_to_doc(instance)
        resp = op.index(index=idx, id=instance.pk, body=doc, refresh="wait_for")
        print(f"Indexed tip {instance.pk} into {idx}: result = {resp.get('result')}")
    except Exception as exc:
        print(Fore.RED + f"[ERROR] Failed to index tip {instance.pk}: {exc}")


class ReviewConfig(AppConfig):
    """
    Django AppConfig for the 'review' app.
    Registers model signal handlers to sync with OpenSearch.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "review"

    def ready(self):
        from review.models import Review, Tip

        # Register signal handlers for Review
        post_save.connect(sync_review, sender=Review, dispatch_uid="sync_review_save")
        post_delete.connect(sync_review, sender=Review, dispatch_uid="sync_review_delete")

        # Register signal handlers for Tip
        post_save.connect(sync_tip, sender=Tip, dispatch_uid="sync_tip_save")
        post_delete.connect(sync_tip, sender=Tip, dispatch_uid="sync_tip_delete")
