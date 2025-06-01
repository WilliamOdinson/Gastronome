import urllib3

from django.conf import settings
from django.core.management.base import BaseCommand
from opensearchpy import OpenSearch, helpers
from tqdm import tqdm

from review.models import Review

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "analysis": {
            "analyzer": {
                "text_ngram": {
                    "tokenizer": "edge_ngram_tokenizer",
                    "filter": ["lowercase"]
                }
            },
            "tokenizer": {
                "edge_ngram_tokenizer": {
                    "type": "edge_ngram",
                    "min_gram": 3,
                    "max_gram": 20,
                    "token_chars": ["letter", "digit"]
                }
            },
        },
    },
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "review_id": {"type": "keyword"},
            "user_id": {"type": "keyword"},
            "user_name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {"ng": {"type": "text", "analyzer": "text_ngram"},
                           "keyword": {"type": "keyword"}}
            },
            "business_id": {"type": "keyword"},
            "business_name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {"ng": {"type": "text", "analyzer": "text_ngram"},
                           "keyword": {"type": "keyword"}}
            },
            "stars": {"type": "integer"},
            "date": {"type": "date"},
            "text": {
                "type": "text",
                "analyzer": "english",
                "fields": {
                    "ng": {"type": "text", "analyzer": "text_ngram"},
                    "keyword": {"type": "keyword"}
                }
            },
            "auto_score": {"type": "float"},
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
    help = "Create OpenSearch index and bulk import all Review records"

    def handle(self, *_, **__):
        op = client()
        index = settings.OPENSEARCH["REVIEW_INDEX"]

        if not op.indices.exists(index):
            op.indices.create(index, body=MAPPING)

        total = Review.objects.count()

        qs = (
            Review.objects.select_related("user", "business")
            .only(
                "review_id",
                "stars",
                "date",
                "text",
                "auto_score",
                "user__user_id",
                "user__display_name",
                "business__business_id",
                "business__name",
            )
            .iterator(chunk_size=1000)
        )

        def docs():
            for r in tqdm(
                qs,
                total=total,
                desc="Indexing Reviews",
                unit="reviews",
                dynamic_ncols=True,
                bar_format=f"{{desc}}: {{n:,}} / {total:,} {{unit}} [{{elapsed}}, {{rate_fmt}}]",
            ):
                yield {
                    "_index": index,
                    "_id": r.pk,
                    "_source": {
                        "review_id": r.review_id,
                        "user_id": r.user.user_id,
                        "user_name": r.user.display_name or r.user.email,
                        "business_id": r.business.business_id,
                        "business_name": r.business.name,
                        "stars": r.stars,
                        "date": r.date,
                        "text": r.text,
                        "auto_score": r.auto_score,
                    },
                }

        helpers.bulk(op, docs(), chunk_size=1000)
        self.stdout.write(self.style.SUCCESS("Successfully indexed all reviews to OpenSearch"))
