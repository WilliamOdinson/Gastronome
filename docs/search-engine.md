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

Without explicit optimization, Django fetches each business’s related categories individually, resulting in many unnecessary database hits. With many matching businesses, database load quickly escalates, significantly reducing performance.

> [!NOTE]
>
> Fortunately, our monitoring with Sentry continuously identifies and reports occurrences of N+1 queries, allowing timely optimization. For further insights, see the [Sentry documentation on N+1 Queries](https://docs.sentry.io/product/issues/issue-details/performance-issues/n-one-queries/).
