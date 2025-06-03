from django.conf import settings
from django.core.management.base import BaseCommand
from opensearchpy import helpers
from tqdm import tqdm

from user.models import User
from Gastronome.opensearch import get_opensearch_client

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
            "useful": {"type": "integer"},
            "funny": {"type": "integer"},
            "cool": {"type": "integer"},
            "fans": {"type": "integer"},
            "average_stars": {"type": "float"},
            "elite_years": {"type": "integer"},
            "compliment_hot": {"type": "integer"},
            "compliment_more": {"type": "integer"},
            "compliment_profile": {"type": "integer"},
            "compliment_cute": {"type": "integer"},
            "compliment_list": {"type": "integer"},
            "compliment_note": {"type": "integer"},
            "compliment_plain": {"type": "integer"},
            "compliment_cool": {"type": "integer"},
            "compliment_funny": {"type": "integer"},
            "compliment_writer": {"type": "integer"},
            "compliment_photos": {"type": "integer"},
            "is_staff": {"type": "boolean"},
            "is_superuser": {"type": "boolean"},
            "is_active": {"type": "boolean"},
            "date_joined": {"type": "date"},
        },
    },
}


class Command(BaseCommand):
    help = "Create OpenSearch index and bulk import all User records"

    def handle(self, *_, **__):
        op = get_opensearch_client()
        index = settings.OPENSEARCH["USER_INDEX"]

        if not op.indices.exists(index):
            op.indices.create(index, body=MAPPING)

        total = User.objects.count()
        qs = User.objects.only(
            "pk",
            "user_id",
            "email",
            "display_name",
            "review_count",
            "useful",
            "funny",
            "cool",
            "fans",
            "average_stars",
            "elite_years",
            "compliment_hot",
            "compliment_more",
            "compliment_profile",
            "compliment_cute",
            "compliment_list",
            "compliment_note",
            "compliment_plain",
            "compliment_cool",
            "compliment_funny",
            "compliment_writer",
            "compliment_photos",
            "is_staff",
            "is_superuser",
            "is_active",
            "date_joined",
        ).iterator(chunk_size=1000)

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
                        "useful": u.useful,
                        "funny": u.funny,
                        "cool": u.cool,
                        "fans": u.fans,
                        "average_stars": u.average_stars,
                        "elite_years": u.elite_years,
                        "compliment_hot": u.compliment_hot,
                        "compliment_more": u.compliment_more,
                        "compliment_profile": u.compliment_profile,
                        "compliment_cute": u.compliment_cute,
                        "compliment_list": u.compliment_list,
                        "compliment_note": u.compliment_note,
                        "compliment_plain": u.compliment_plain,
                        "compliment_cool": u.compliment_cool,
                        "compliment_funny": u.compliment_funny,
                        "compliment_writer": u.compliment_writer,
                        "compliment_photos": u.compliment_photos,
                        "is_staff": u.is_staff,
                        "is_superuser": u.is_superuser,
                        "is_active": u.is_active,
                        "date_joined": u.date_joined,
                    },
                }

        helpers.bulk(op, docs(), chunk_size=1000)
        self.stdout.write(self.style.SUCCESS("Successfully indexed all users to OpenSearch"))
