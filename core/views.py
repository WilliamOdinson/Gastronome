from collections import defaultdict
from datetime import datetime
from hashlib import blake2s

from django.core.cache import cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from business.models import Business, Category
from .context_processors import CATEGORY_KEYWORDS, RATING_FILTERS


def index(request):
    cache_key = "US_category_counts"
    category_counts = cache.get(cache_key)

    if category_counts is None:
        category_counts = {}
        for label, keywords in CATEGORY_KEYWORDS.items():
            q = Q()
            for kw in keywords:
                q |= Q(name__icontains=kw)
            matched_cats = Category.objects.filter(q).distinct()

            business_ids = set()
            for cat in matched_cats:
                business_ids.update(cat.businesses.values_list("business_id", flat=True))

            category_counts[label] = len(business_ids)

        cache.set(cache_key, category_counts, timeout=86400)

    return render(request, "index.html", {
        "category_counts": category_counts
    })


def tech_details(request):
    return render(request, 'tech_details.html')

def system_map(request):
    return render(request, 'system_map.html')

def page_not_found(request, exception):
    return render(request, '404.html', status=404)

def server_error(request):
    return HttpResponse("Server Error (500)", status=500)

def permission_denied(request, exception):
    return HttpResponse("Permission Denied (403)", status=403)

def bad_request(request, exception):
    return HttpResponse("Bad Request (400)", status=400)

def search(request):
    """
    Main entry point for search: filters businesses by "what", "where", and category.
    """
    q = request.GET.get("q", "").strip()
    where = request.GET.get("where", "").strip() or "PA"
    cat_label = request.GET.get("category", "All").strip()

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
            keywords = CATEGORY_KEYWORDS.get(cat_label,
                                             [cat_label.lower()])
            cat_q = Q()
            for kw in keywords:
                cat_q |= Q(categories__name__icontains=kw)
            qs = qs.filter(cat_q)

        qs = qs.distinct().prefetch_related("categories",
                                            "photos", "hours")

        now = timezone.localtime()
        weekday = now.strftime("%A")
        current_time = now.time()

        results_raw = []
        for biz in qs:
            photo = biz.photos.first()
            open_now = (
                biz.is_open and
                biz.hours.filter(day=weekday,
                                 open_time__lte=current_time,
                                 close_time__gte=current_time).exists()
            )

            results_raw.append({
                "id": biz.pk,
                "name": biz.name,
                "categories": ", ".join(
                    c.name for c in biz.categories.all()[:3]),
                "address": f"{biz.address}, {biz.city}",
                "latitude": float(biz.latitude),
                "longitude": float(biz.longitude),
                "stars": biz.stars,
                "review_count": biz.review_count,
                "is_open_now": open_now,
                "image_url": (photo.image_url if photo
                              else "https://placehold.co/600x400"),
            })

        cache.set(cache_key, results_raw)

    paginator = Paginator(results_raw, 20)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "results": page_obj.object_list,
        "page_obj": page_obj,
        "result_count": paginator.count,
        "q": q,
        "where": where,
        "category": cat_label,
        "rating_labels": RATING_FILTERS,
    }
    return render(request, "search_results.html", context)


def _make_cache_key(q: str, where: str, cat: str) -> str:
    """
    Generate a short cache key: search:<8-byte-hash>
    """
    raw = f"{q}|{where}|{cat}".encode()
    digest = blake2s(raw, digest_size=8).hexdigest()
    return f"search:{digest}"
