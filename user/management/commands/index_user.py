import urllib3

from django.conf import settings
from django.core.management.base import BaseCommand
from opensearchpy import OpenSearch, helpers
from tqdm import tqdm

from user.models import User

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "analysis": {
            "analyzer": {
                "name_ngram": {
                    "tokenizer": "edge_ngram_tokenizer",
                    "filter": ["lowercase"]
                }
            },
            "tokenizer": {
                "edge_ngram_tokenizer": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 20,
                    "token_chars": ["letter", "digit"]
                }
            },
        },
    },
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "user_id": {"type": "keyword"},
            "email": {"type": "keyword"},
            "display_name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "ng": {"type": "text", "analyzer": "name_ngram"},
                    "keyword": {"type": "keyword"},
                },
            },
            "review_count": {"type": "integer"},
            "fans": {"type": "integer"},
            "average_stars": {"type": "float"},
            "elite_years": {"type": "integer"},
            "is_staff": {"type": "boolean"},
            "is_superuser": {"type": "boolean"},
            "is_active": {"type": "boolean"},
            "date_joined": {"type": "date"},
        },
    },
}


def client():
    return OpenSearch(
        hosts=[settings.OPENSEARCH["HOST"]],
        http_auth=(settings.OPENSEARCH["USER"], settings.OPENSEARCH["PASSWORD"]),
        verify_certs=False,
        retry_on_timeout=True,
        timeout=30,
    )


class Command(BaseCommand):
    help = "Create OpenSearch index and bulk import all User records"

    def handle(self, *_, **__):
        op = client()
        index = settings.OPENSEARCH["USER_INDEX"]

        if not op.indices.exists(index):
            op.indices.create(index, body=MAPPING)

        total = User.objects.count()
        qs = (
            User.objects.only(
                "pk",
                "user_id",
                "email",
                "display_name",
                "review_count",
                "fans",
                "average_stars",
                "elite_years",
                "is_staff",
                "is_superuser",
                "is_active",
                "date_joined",
            ).iterator(chunk_size=1000)
        )

        def docs():
            for u in tqdm(
                qs,
                total=total,
                desc="Indexing Users",
                unit="users",
                dynamic_ncols=True,
                bar_format=f"{{desc}}: {{n:,}} / {total:,} {{unit}} [{{elapsed}}, {{rate_fmt}}]",
            ):
                yield {
                    "_index": index,
                    "_id": u.pk,
                    "_source": {
                        "user_id": u.user_id,
                        "email": u.email,
                        "display_name": u.display_name,
                        "review_count": u.review_count,
                        "fans": u.fans,
                        "average_stars": u.average_stars,
                        "elite_years": u.elite_years,
                        "is_staff": u.is_staff,
                        "is_superuser": u.is_superuser,
                        "is_active": u.is_active,
                        "date_joined": u.date_joined,
                    },
                }

        helpers.bulk(op, docs(), chunk_size=1000)
        self.stdout.write(self.style.SUCCESS("Successfully indexed all users to OpenSearch"))
