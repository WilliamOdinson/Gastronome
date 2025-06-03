import urllib3

from colorama import Fore, init
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from opensearchpy import OpenSearch, NotFoundError


init(autoreset=True)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def client():
    return OpenSearch(
        hosts=[settings.OPENSEARCH["HOST"]],
        http_auth=(settings.OPENSEARCH["USER"], settings.OPENSEARCH["PASSWORD"]),
        verify_certs=False,
        retry_on_timeout=True,
        timeout=10,
    )


class Command(BaseCommand):
    help = (
        "Delete a specific OpenSearch index. "
        "You can pass a full index name (e.g. 'gastronome-review') "
        "or a symbolic key from settings.OPENSEARCH (e.g. 'REVIEW_INDEX')."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "index",
            type=str,
            help="Index name or settings.OPENSEARCH key (e.g. 'REVIEW_INDEX')"
        )

    def handle(self, *args, **options):
        index_arg = options["index"]
        os_settings = getattr(settings, "OPENSEARCH", {})

        # Support both direct index names and symbolic keys like 'REVIEW_INDEX'
        index_name = os_settings.get(index_arg.upper(), index_arg)

        op = client()

        try:
            if op.indices.exists(index=index_name):
                self.stdout.write(f"Deleting index: {index_name}...")
                op.indices.delete(index=index_name)
                self.stdout.write(f"[INFO] Index '{index_name}' deleted successfully.")
            else:
                self.stdout.write(Fore.YELLOW + f"[WARNING] Index '{index_name}' does not exist.")
        except NotFoundError:
            self.stdout.write(Fore.YELLOW + f"[WARNING] Index '{index_name}' not found.")
        except Exception as exc:
            raise CommandError(Fore.RED + f"[ERROR] Failed to delete index '{index_name}': {exc}")
