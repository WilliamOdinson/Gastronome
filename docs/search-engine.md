# Search Engine Implementation

This document dives into why we use OpenSearch instead of relying solely on Django ORM for the admin backends and business search functionality.

## The N+1 Query Problem

The infamous **"N+1 query"** problem occurs when Django's ORM retrieves related data by making separate database queries for each object, instead of batching them into a single, efficient query. This significantly increases the number of database interactions, degrading the application's performance.

In our project, we encountered this issue in `core/views.py` while implementing search functionality that allows users to find businesses by their name, category, or location. An initial implementation that introduced the N+1 issue was as follows (resolved earlier in [commit 8898e6c](https://github.com/WilliamOdinson/Gastronome/commit/8898e6cccd0a506cc0e7f4655bdf02c79b87fc60)):

```python
cache_key = _make_cache_key(q, where, cat_label)
results_raw = cache.get(cache_key)

if results_raw is None:
    qs = Business.objects.all()

    if q:
        qs = qs.filter(Q(name__icontains=q) |
                       Q(categories__name__icontains=q))

    if where:
        toks = where.split()
        if len(toks) == 1:
            qs = qs.filter(Q(state__iexact=toks[0]) |
                           Q(city__icontains=toks[0]))
        else:
            qs = qs.filter(city__icontains=" ".join(toks[:-1]),
                           state__iexact=toks[-1])

    if cat_label and cat_label != "All":
        keywords = CATEGORY_KEYWORDS.get(cat_label, [cat_label.lower()])
        cat_q = Q()
        for kw in keywords:
            cat_q |= Q(categories__name__icontains=kw)
        qs = qs.filter(cat_q)
```

Specifically, the problematic part is the filtering by categories:

```python
if cat_label and cat_label != "All":
    keywords = CATEGORY_KEYWORDS.get(cat_label, [cat_label.lower()])
    cat_q = Q()
    for kw in keywords:
        cat_q |= Q(categories__name__icontains=kw)
    qs = qs.filter(cat_q)
```

This snippet triggers the N+1 problem because it implicitly causes:

- **1 initial query** to fetch matching businesses.
- **N additional queries** when iterating over these businesses if accessing related fields (such as `categories`) without proper prefetching or selecting related objects.

Without explicit optimization, Django fetches each business's related categories individually, resulting in many unnecessary database hits. With many matching businesses, database load quickly escalates, significantly reducing performance.

> [!NOTE]
>
> Fortunately, our monitoring with Sentry continuously identifies and reports occurrences of N+1 queries, allowing timely optimization. For further insights, see the [Sentry documentation on N+1 Queries](https://docs.sentry.io/product/issues/issue-details/performance-issues/n-one-queries/).

## Scalability Constraints

In our admin tables, certain datasets - such as reviews - can quickly grow enormous. For example, the reviews table imported contains approximately 6,990,280 entries, making SQL-based queries increasingly expensive and slow.

To manage scalability and maintain performance, we integrated OpenSearch, allowing us to define custom indexing and query strategies optimized for rapid searching across large, structured, and unstructured datasets. Below, we outline the a complex mapping we implemented for explanation.

**Business Mapping**  (`business/management/commands/index_business.py`)

```python
MAPPING = {
    "settings": {
        # One shard chosen for simplicity and management ease; adjust for scaling.
        "number_of_shards": 1,
        "analysis": {
            "analyzer": {
                # Analyzer that tokenizes text into edge n-grams for partial matching (autocomplete).
                "name_ngram": {
                    "tokenizer": "edge_ngram_tokenizer",
                    "filter": ["lowercase"]
                }
            },
            "tokenizer": {
                "edge_ngram_tokenizer": {
                    "type": "edge_ngram",
                    "min_gram": 2,   # Minimum character length for n-gram.
                    "max_gram": 20,  # Maximum character length for n-gram.
                    "token_chars": ["letter", "digit"]  # Characters included in tokens.
                }
            },
        },
    },
    "mappings": {
        "properties": {
            # Unique ID for the business, optimized as keyword (exact matching).
            "business_id": {"type": "keyword"},
            # Business name field, with standard analysis plus n-gram and exact keyword subfields.
            "name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "ng": {"type": "text", "analyzer": "name_ngram"},
                    "keyword": {"type": "keyword"},
                },
            },
            # City and state for exact matching queries.
            "city": {"type": "keyword"},
            "state": {"type": "keyword"},
            # Geographic coordinates for efficient spatial searches.
            "location": {"type": "geo_point"},
            # Ratings and review count stored numerically for range queries.
            "stars": {"type": "float"},
            "review_count": {"type": "integer"},
            # Boolean to quickly filter by open status.
            "is_open": {"type": "boolean"},
            # Categories with English analysis and edge-ngram for autocomplete and precise filtering.
            "categories": {
                "type": "text",
                "analyzer": "english",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "ng": {"type": "text", "analyzer": "name_ngram"}
                }
            },
        }
    },
}
```

By defining and leveraging these OpenSearch mappings, we can efficiently query vast datasets, mitigating SQL-related scalability issues and significantly enhancing performance in search-intensive scenarios.
