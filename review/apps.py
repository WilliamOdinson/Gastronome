import logging
import urllib3

from colorama import Fore, Style, init
from opensearchpy import NotFoundError, OpenSearch

from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import m2m_changed, post_delete, post_save


init(autoreset=True)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


def client():
    return OpenSearch(
        hosts=[settings.OPENSEARCH["HOST"]],
        http_auth=(settings.OPENSEARCH["USER"], settings.OPENSEARCH["PASSWORD"]),
        verify_certs=False,
        retry_on_timeout=True,
        timeout=10,
    )


def _review_to_doc(r):
    """
    Convert the Review object to an OpenSearch document.
    """
    if r.auto_score is None:
        r.auto_score = 0.0
    return {
        "review_id": r.review_id,
        "user_id": r.user_id,
        "user_name": r.user.display_name or r.user.email,
        "business_id": r.business_id,
        "business_name": r.business.name,
        "stars": r.stars,
        "date": r.date,
        "text": r.text,
        "auto_score": r.auto_score,
    }


def sync_review(sender, instance, **kwargs):
    if settings.DJANGO_TEST or settings.DATA_IMPORT:
        # print(Fore.YELLOW + f"[SKIP] OpenSearch indexing skipped")or settings
        return
    op = client()
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
        resp = op.index(
            index=idx,
            id=instance.pk,
            body=_review_to_doc(instance),
            refresh="wait_for")
        print(f"Indexed review {instance.pk} into {idx}: result = {resp.get('result')}")
    except Exception as exc:
        print(Fore.RED + f"[ERROR] Failed to index review {instance.pk}: {exc}")


def _tip_to_doc(t):
    """
    Convert the Tip object to an OpenSearch document.
    """
    return {
        "user_id": t.user_id,
        "user_name": t.user.display_name or t.user.email,
        "business_id": t.business_id,
        "business_name": t.business.name,
        "date": t.date,
        "text": t.text,
        "compliment_count": t.compliment_count,
    }


def sync_tip(sender, instance, **kwargs):
    if settings.DJANGO_TEST:
        # print(Fore.YELLOW + f"[SKIP] OpenSearch indexing skipped")or settings
        return
    op = client()
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
        resp = op.index(index=idx, id=instance.pk, body=_tip_to_doc(instance), refresh="wait_for")
        print(f"Indexed tip {instance.pk} into {idx}: result = {resp.get('result')}")
    except Exception as exc:
        print(Fore.RED + f"[ERROR] Failed to index tip {instance.pk}: {exc}")


class ReviewConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "review"

    def ready(self):
        from review.models import Review, Tip

        post_save.connect(sync_review, sender=Review,
                          dispatch_uid="sync_review_save")
        post_delete.connect(sync_review, sender=Review,
                            dispatch_uid="sync_review_delete")

        post_save.connect(sync_tip, sender=Tip,
                          dispatch_uid="sync_tip_save")
        post_delete.connect(sync_tip, sender=Tip,
                            dispatch_uid="sync_tip_delete")
