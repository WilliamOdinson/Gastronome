from django.conf import settings
from opensearchpy import OpenSearch

from core.context_processors import CATEGORY_KEYWORDS
from Gastronome.opensearch import get_opensearch_client


def search_business(q, city, state, category, page, per_page=20):
    """
    Perform OpenSearch query with optional full-text and category filtering.
    """
    must, filt = [], []

    if q:
        must.append({
            "multi_match": {
                "query": q,
                "fields": [
                    "name^4",
                    "name.ng",
                    "categories^2"
                ],
                "fuzziness": "AUTO"
            }
        })

    if city:
        filt.append({"term": {"city": city}})
    if state:
        filt.append({"term": {"state": state}})
    if category and category != "All":
        keywords = CATEGORY_KEYWORDS.get(category, [category])
        must.append({
            "bool": {
                "should": [{"match": {"categories": kw}} for kw in keywords],
                "minimum_should_match": 1
            }
        })

    body = {
        "query": {
            "bool": {
                "must": must if must else [{"match_all": {}}],
                "filter": filt
            }
        },
        "from": (page - 1) * per_page,
        "size": per_page,
    }

    res = get_opensearch_client().search(index=settings.OPENSEARCH["BUSINESS_INDEX"], body=body)
    ids = [hit["_id"] for hit in res["hits"]["hits"]]
    return res["hits"]["total"]["value"], ids
