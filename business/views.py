from django.shortcuts import render, get_object_or_404
from .models import Business
from django.conf import settings
from review.models import Review

def business_detail(request, business_id):
    """
    Display detailed information of a single business.
    """
    business = get_object_or_404(Business, pk=business_id)
    business.stars = round(business.stars, 2)
    recent_checkins = business.checkins.order_by('-checkin_time')[:10]
    reviews = business.reviews.select_related('user').order_by('-date')[:50]
    return render(request, 'business_detail.html', {
        'business': business,
        'recent_checkins': recent_checkins,
        'reviews': reviews,
    })
