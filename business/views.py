import hashlib
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

    return render(request, 'business_detail.html', {
        'business': business,
        'recent_checkins': recent_checkins,
        'reviews': reviews,
        "user_has_review": user_has_review,
    })
