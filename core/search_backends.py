import urllib3

from django.conf import settings
from opensearchpy import OpenSearch


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def client():
    """Return an OpenSearch client."""
    return OpenSearch(
        hosts=[settings.OPENSEARCH["HOST"]],
        http_auth=(settings.OPENSEARCH["USER"], settings.OPENSEARCH["PASSWORD"]),
        verify_certs=False,
        retry_on_timeout=True,
        timeout=15,
    )


def search_business(q, city, state, category, page, per_page=20):
    """
    Return (total, [business_id,  ...]), keeping OpenSearch order.
    """
    must = []
    filt = []

    if q:
        must.append({
            "multi_match": {
                "query": q,
                "fields": ["name^4", "name.ng"],
                "fuzziness": "AUTO"
            }
        })

    if city:
        filt.append({"term": {"city": city}})
    if state:
        filt.append({"term": {"state": state}})
    if category and category != "All":
        filt.append({"term": {"categories": category}})

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

    res = client().search(index=settings.OPENSEARCH["INDEX"], body=body)
    ids = [hit["_id"] for hit in res["hits"]["hits"]]
    return res["hits"]["total"]["value"], ids
