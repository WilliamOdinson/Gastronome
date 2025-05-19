import urllib3

from django.conf import settings
from django.core.management.base import BaseCommand
from opensearchpy import OpenSearch, helpers
from tqdm import tqdm

from business.models import Business

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "index.max_result_window": 1000000,  # Allows deep pagination beyond 10,000
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
        "properties": {
            "business_id": {"type": "keyword"},
            "name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "ng": {"type": "text", "analyzer": "name_ngram"},
                    "keyword": {"type": "keyword"},
                },
            },
            "city": {"type": "keyword"},
            "state": {"type": "keyword"},
            "location": {"type": "geo_point"},
            "stars": {"type": "float"},
            "review_count": {"type": "integer"},
            "is_open": {"type": "boolean"},
            "categories": {"type": "keyword"},
        }
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
    help = "Create OpenSearch index and bulk import all Business records"

    def handle(self, *_, **__):
        op = client()
        index = settings.OPENSEARCH["INDEX"]

        # Create the index if it doesn't exist
        if not op.indices.exists(index):
            op.indices.create(index, body=MAPPING)

        total = Business.objects.count()
        qs = Business.objects.prefetch_related("categories").iterator(chunk_size=1000)

        def docs():
            """Yield OpenSearch bulk actions with a clean progress bar"""
            for b in tqdm(
                qs,
                total=total,
                desc="Indexing to OpenSearch",
                unit="businesses",
                dynamic_ncols=True,
                bar_format=f"{{desc}}: {{n:,}} / {total:,} {{unit}} [{{elapsed}}, {{rate_fmt}}]"
            ):
                yield {
                    "_index": index,
                    "_id": b.business_id,
                    "_source": {
                        "business_id": b.business_id,
                        "name": b.name,
                        "city": b.city,
                        "state": b.state,
                        "location": {
                            "lat": float(b.latitude),
                            "lon": float(b.longitude),
                        },
                        "stars": b.stars,
                        "review_count": b.review_count,
                        "is_open": b.is_open,
                        "categories": list(b.categories.values_list("name", flat=True)),
                    },
                }

        helpers.bulk(op, docs(), chunk_size=1000)
        self.stdout.write(self.style.SUCCESS("Successfully indexed all businesses to OpenSearch"))
