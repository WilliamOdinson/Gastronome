from django.conf import settings
from django.core.management.base import BaseCommand
from opensearchpy import helpers
from tqdm import tqdm

from review.models import Tip
from Gastronome.opensearch import get_opensearch_client


TIP_MAPPING = {
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
            "user_id": {"type": "keyword"},
            "user_name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "ng": {"type": "text", "analyzer": "text_ngram"},
                    "keyword": {"type": "keyword"}
                },
            },
            "business_id": {"type": "keyword"},
            "business_name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "ng": {"type": "text", "analyzer": "text_ngram"},
                    "keyword": {"type": "keyword"}
                },
            },
            "date": {"type": "date"},
            "text": {"type": "text", "analyzer": "english"},
            "compliment_count": {"type": "integer"},
        },
    },
}


class Command(BaseCommand):
    help = "Create OpenSearch index and bulk import all Tip records"

    def handle(self, *_, **__):
        op = get_opensearch_client()
        index = settings.OPENSEARCH["TIP_INDEX"]

        if not op.indices.exists(index):
            op.indices.create(index, body=TIP_MAPPING)

        total = Tip.objects.count()
        qs = (
            Tip.objects.select_related("user", "business")
            .only(
                "text",
                "date",
                "compliment_count",
                "user__user_id",
                "user__display_name",
                "business__business_id",
                "business__name",
            )
            .iterator(chunk_size=1000)
        )

        def docs():
            for t in tqdm(
                qs,
                total=total,
                desc="Indexing Tips",
                unit="tips",
                dynamic_ncols=True,
                bar_format=f"{{desc}}: {{n:,}} / {total:,} {{unit}} [{{elapsed}}, {{rate_fmt}}]",
            ):
                yield {
                    "_index": index,
                    "_id": t.pk,
                    "_source": {
                        "user_id": t.user.user_id,
                        "user_name": t.user.display_name or t.user.email,
                        "business_id": t.business.business_id,
                        "business_name": t.business.name,
                        "date": t.date,
                        "text": t.text,
                        "compliment_count": t.compliment_count,
                    },
                }

        helpers.bulk(op, docs(), chunk_size=1000)
        self.stdout.write(self.style.SUCCESS("Successfully indexed all tips to OpenSearch"))
