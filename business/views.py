from ast import literal_eval
import hashlib
import json
import pickle

from django.core.cache import cache
from django.shortcuts import get_object_or_404, render

from business.models import Business
from review.models import Review


def business_detail(request, business_id):
    """
    Display detailed information of a single business.
    """
    cache_key = f"biz_detail:{business_id}"
    cached = cache.get(cache_key)

    if cached:
        business, recent_checkins, reviews = pickle.loads(cached)
    else:
        business = get_object_or_404(Business, pk=business_id)
        business.stars = round(business.stars, 2)
        recent_checkins = business.checkins.order_by('-checkin_time')[:10]
        reviews = business.reviews.select_related('user').order_by('-date')[:50]
        cache.set(cache_key, pickle.dumps((business, recent_checkins, reviews)), timeout=86400)

    user_has_review = False
    if request.user.is_authenticated:
        user_has_review = business.reviews.filter(user=request.user).exists()
    hours = business.hours.values('day', 'open_time', 'close_time')
    hours_json = [
        {
            'day': h['day'],
            'open_time': h['open_time'].strftime('%H:%M'),
            'close_time': h['close_time'].strftime('%H:%M'),
        }
        for h in hours
    ]
    raw_attributes = business.attributes or {}
    parsed_amenities = parse_amenities(raw_attributes)
    split_index = (len(parsed_amenities) + 1) // 2
    rating_range = range(1, 6)

    return render(request, 'business_detail.html', {
        'business': business,
        'recent_checkins': recent_checkins,
        'reviews': reviews,
        'rating_range': rating_range,
        "user_has_review": user_has_review,
        'hours_json': json.dumps(hours_json),
        'parsed_amenities': parsed_amenities,
        'amenities_split_index': split_index,
    })


def parse_amenities(attributes: dict) -> list[str]:
    amenities = []

    def flatten(k, v):
        """Flatten nested dict entries and handle value types"""
        if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
            try:
                v = literal_eval(v)
            except Exception:
                return  # skip invalid dict string
        if isinstance(v, dict):
            for subk, subv in v.items():
                flatten(f"{k}.{subk}", subv)
        else:
            if str(v) in ["False", "None", "u'none'", "'no'", "no", "none", "", None]:
                return
            if str(v) == "True":
                amenities.append(k)
            else:
                amenities.append(f"{k}: {v}")

    for key, value in attributes.items():
        flatten(key, value)

    return amenities
