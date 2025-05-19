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
from core.context_processors import CATEGORY_KEYWORDS, RATING_FILTERS
from core.search_backends import search_business
from recommend.services import fetch_recommendations


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

    state = request.GET.get("state", "PA")
    rec_qs = fetch_recommendations(request.user, state=state, n=8)

    return render(request, "index.html", {
        "category_counts": category_counts,
        "rec_businesses": rec_qs,
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
    q = request.GET.get("q", "").strip()
    where = request.GET.get("where", "").strip() or "PA"
    toks = where.split()
    city = None
    state = None
    if len(toks) == 1:
        state = toks[0].upper()
    else:
        city = " ".join(toks[:-1])
        state = toks[-1].upper()

    cat_label = request.GET.get("category", "All").strip()
    page = int(request.GET.get("page", 1))

    now = timezone.localtime()
    weekday = now.strftime("%A")
    now_time = now.time()

    ck = _cache_key(q, city, state, cat_label) + f":p{page}"
    cached = cache.get(ck)
    if cached:
        total, cards = cached
    else:
        total, id_list = search_business(q, city, state, cat_label, page)
        objs = Business.objects.in_bulk(id_list)
        cards = [_build_card(objs[i], weekday, now_time) for i in id_list if i in objs]
        cache.set(ck, (total, cards), 3600)

    paginator = Paginator(range(total), 20)
    page_obj = paginator.page(page)

    context = {
        "results": cards,
        "page_obj": page_obj,
        "result_count": total,
        "q": q,
        "where": where,
        "category": cat_label,
        "rating_labels": RATING_FILTERS,
    }
    return render(request, "search_results.html", context)


def _cache_key(q, city, state, cat):
    raw = f"{q}|{city}|{state}|{cat}".encode()
    return "os:" + blake2s(raw, digest_size=8).hexdigest()


def _build_card(biz, weekday, now_time):
    """
    Serialize the Business object into a template-friendly dict.
    """
    photo = biz.photos.first()
    open_now = (
        biz.is_open
        and biz.hours.filter(day=weekday,
                             open_time__lte=now_time,
                             close_time__gte=now_time).exists()
    )
    return {
        "business_id": biz.business_id,
        "name": biz.name,
        "categories": ", ".join(biz.categories.values_list("name", flat=True)[:3]),
        "address": f"{biz.address}, {biz.city}",
        "latitude": float(biz.latitude),
        "longitude": float(biz.longitude),
        "stars": biz.stars,
        "review_count": biz.review_count,
        "is_open_now": open_now,
        "image_url": (photo.image_url if photo else "https://placehold.co/600x400"),
    }
