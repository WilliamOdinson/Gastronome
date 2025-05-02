from collections import defaultdict
from django.shortcuts import render
from django.core.cache import cache
from django.db.models import Q
from business.models import Category

CATEGORY_KEYWORDS = {
    "Shops": ["shop"],
    "Hotels": ["hotel"],
    "Restaurants": ["restaurant"],
    "Bars": ["bar"],
    "Fitness": ["fitness", "gym", "exercise"],
    "Events": ["event"],
}

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
