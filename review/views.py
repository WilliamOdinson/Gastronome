import uuid

from django.core.cache import cache
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, get_object_or_404, render
from django.db import transaction
from django.db.models import F
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from business.models import Business
from .models import Review
from .forms import ReviewForm
from api.inference import predict_score


@transaction.atomic
def create_review(request, business_id):
    if not request.user.is_authenticated:
        return redirect("user:login")

    business = get_object_or_404(Business, pk=business_id)

    if Review.objects.filter(user=request.user, business=business).exists():
        return HttpResponseBadRequest("You have already reviewed this business.")

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.business = business
            review.review_id = uuid.uuid4().hex[:22]
            review.auto_score = predict_score(review.text)
            review.save()

            b_old_cnt = business.review_count
            b_old_avg = business.stars or 0.0
            b_new_cnt = b_old_cnt + 1
            business.review_count = F("review_count") + 1
            business.stars = ((b_old_avg * b_old_cnt) + review.stars) / b_new_cnt
            business.save(update_fields=["review_count", "stars"])
            
            cache.delete(f"biz_detail:{business.business_id}")

            u_old_cnt = request.user.review_count
            u_old_avg = request.user.average_stars or 0.0
            u_new_cnt = u_old_cnt + 1
            request.user.review_count = F("review_count") + 1
            request.user.average_stars = ((u_old_avg * u_old_cnt) + review.stars) / u_new_cnt
            request.user.save(update_fields=["review_count", "average_stars"])

            return redirect("business:business_detail", business_id=business_id)
    else:
        form = ReviewForm()

    return render(request, "create_review.html", {"form": form, "business": business})


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def delete_review(request, review_id):
    review = get_object_or_404(Review, pk=review_id, user=request.user)
    business = review.business

    b_old_cnt = business.review_count
    b_old_avg = business.stars or 0.0
    u_old_cnt = request.user.review_count
    u_old_avg = request.user.average_stars or 0.0
    removed_stars = review.stars

    review.delete()

    b_new_cnt = max(b_old_cnt - 1, 0)
    business.review_count = F("review_count") - 1
    if b_new_cnt:
        business.stars = ((b_old_avg * b_old_cnt) - removed_stars) / b_new_cnt
    else:
        business.stars = 0.0
    business.save(update_fields=["review_count", "stars"])
    
    cache.delete(f"biz_detail:{business.business_id}")

    u_new_cnt = max(u_old_cnt - 1, 0)
    request.user.review_count = F("review_count") - 1
    if u_new_cnt:
        request.user.average_stars = ((u_old_avg * u_old_cnt) - removed_stars) / u_new_cnt
    else:
        request.user.average_stars = 0.0
    request.user.save(update_fields=["review_count", "average_stars"])

    return redirect("user:profile")
