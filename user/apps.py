import logging
import urllib3

from colorama import Fore, Style, init
from opensearchpy import NotFoundError, OpenSearch

from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_delete, post_save


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


def _to_doc(user):
    return {
        "user_id": user.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "review_count": user.review_count,
        "fans": user.fans,
        "average_stars": user.average_stars,
        "elite_years": user.elite_years,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "is_active": user.is_active,
        "date_joined": user.date_joined,
    }


def sync_user_to_opensearch(sender, instance, **kwargs):
    if settings.DJANGO_TEST or settings.DATA_IMPORT:
        # print(Fore.YELLOW + f"[SKIP] OpenSearch indexing skipped")or settings
        return
    op = client()
    index = settings.OPENSEARCH["USER_INDEX"]

    # Handle delete signal
    if kwargs.get("signal") == post_delete:
        try:
            op.delete(index=index, id=instance.pk, ignore=[404], refresh="wait_for")
        except NotFoundError:
            pass
        return

    try:
        resp = op.index(
            index=index,
            id=instance.pk,
            body=_to_doc(instance),
            refresh="wait_for",
        )
        print(f"Indexed user {instance.pk} into {index}: result = {resp.get('result')}")
    except Exception as exc:
        print(Fore.RED + f"[ERROR] OpenSearch indexing error for user {instance.pk}: {exc}")


class UserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "user"

    def ready(self):
        from user.models import User
        post_save.connect(sync_user_to_opensearch, sender=User,
                          dispatch_uid="user_to_opensearch_save")
        post_delete.connect(sync_user_to_opensearch, sender=User,
                            dispatch_uid="user_to_opensearch_delete")
