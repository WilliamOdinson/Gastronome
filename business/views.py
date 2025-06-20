import json
import pickle
from ast import literal_eval
from typing import List, Dict

from django.core.cache import cache
from django.shortcuts import get_object_or_404, render

from business.models import Business
from review.models import Review
from recommend.services import log_click, get_click_recommendations


def parse_amenities(attrs: Dict) -> List[str]:
    """
    Turn the nested JSON attributes field into a flat list of printable strings.
    """
    amenities: List[str] = []

    def _flatten(key: str, val):
        # value may be stored as a str representation of a dict
        if isinstance(val, str) and val.startswith("{") and val.endswith("}"):
            try:
                val = literal_eval(val)
            except Exception:
                return

        if isinstance(val, dict):
            for subk, subv in val.items():
                _flatten(f"{key}.{subk}", subv)
        else:
            # skip obvious negatives
            falsy = {"False", "None", "u'none'", "'no'", "no", "none", "", None}
            if str(val) in falsy:
                return
            if str(val) == "True":
                amenities.append(key)
            else:
                amenities.append(f"{key}: {val}")

    for k, v in attrs.items():
        _flatten(k, v)

    return amenities


def business_detail(request, business_id: str):
    """
    Render a single business detail page and record the page-view click.
    """
    cache_key = f"biz_detail:{business_id}"
    cached = cache.get(cache_key)

    if cached:
        business, recent_checkins, reviews = pickle.loads(cached)
    else:
        business = get_object_or_404(Business, pk=business_id)
        business.stars = round(business.stars, 2)
        recent_checkins = business.checkins.order_by("-checkin_time")[:10]
        reviews = (business.reviews.select_related("user").order_by("-date")[:50])
        cache.set(
            cache_key,
            pickle.dumps((business, recent_checkins, reviews)),
            timeout=86400,
        )

    log_click(request, business)
    rec_queryset = get_click_recommendations(business_id, n=8)

    user_has_review = (
        request.user.is_authenticated
        and business.reviews.filter(user=request.user).exists()
    )
    hours = business.hours.values("day", "open_time", "close_time")
    hours_json = [
        {
            "day": h["day"],
            "open_time": h["open_time"].strftime("%H:%M"),
            "close_time": h["close_time"].strftime("%H:%M"),
        }
        for h in hours
    ]
    raw_attributes = business.attributes or {}
    parsed_amenities = parse_amenities(raw_attributes)
    split_index = (len(parsed_amenities) + 1) // 2
    rating_range = range(1, 6)

    return render(
        request,
        "business_detail.html",
        {
            "business": business,
            "recent_checkins": recent_checkins,
            "reviews": reviews,
            "recommendations": rec_queryset,
            "rating_range": rating_range,
            "user_has_review": user_has_review,
            "hours_json": json.dumps(hours_json),
            "parsed_amenities": parsed_amenities,
            "amenities_split_index": split_index,
        },
    )
