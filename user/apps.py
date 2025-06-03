import logging

from colorama import Fore, init
from opensearchpy import NotFoundError

from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_delete, post_save

from Gastronome.opensearch import get_opensearch_client

init(autoreset=True)
logger = logging.getLogger(__name__)


def _to_doc(user):
    return {
        "user_id": user.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "review_count": user.review_count,
        "useful": user.useful,
        "funny": user.funny,
        "cool": user.cool,
        "fans": user.fans,
        "average_stars": user.average_stars,
        "elite_years": user.elite_years,
        "compliment_hot": user.compliment_hot,
        "compliment_more": user.compliment_more,
        "compliment_profile": user.compliment_profile,
        "compliment_cute": user.compliment_cute,
        "compliment_list": user.compliment_list,
        "compliment_note": user.compliment_note,
        "compliment_plain": user.compliment_plain,
        "compliment_cool": user.compliment_cool,
        "compliment_funny": user.compliment_funny,
        "compliment_writer": user.compliment_writer,
        "compliment_photos": user.compliment_photos,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "is_active": user.is_active,
        "date_joined": user.date_joined,
    }


def sync_user_to_opensearch(sender, instance, **kwargs):
    if settings.DJANGO_TEST or settings.DATA_IMPORT:
        # print(Fore.YELLOW + f"[SKIP] OpenSearch indexing skipped")
        return
    op = get_opensearch_client()
    index = settings.OPENSEARCH["USER_INDEX"]

    # Handle delete signal
    if kwargs.get("signal") == post_delete:
        try:
            op.delete(index=index, id=instance.pk, ignore=[404], refresh="wait_for")
        except NotFoundError:
            print(Fore.RED + f"[ERROR] User with ID {instance.pk} not found in OpenSearch.")
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
