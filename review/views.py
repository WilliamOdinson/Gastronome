import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import F, Case, When, Value, FloatField, ExpressionWrapper
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from api.inference import predict_score
from business.models import Business
from review.forms import ReviewForm
from review.models import Review

User = get_user_model()


@transaction.atomic
def create_review(request, business_id: str):
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

            # Statistic Updates: Business
            Business.objects.filter(pk=business.pk).update(
                review_count=F("review_count") + 1,
                stars=(
                    F("stars") * F("review_count") + review.stars
                ) / (F("review_count") + 1),
            )

            # Statistic Updates: User
            User.objects.filter(pk=request.user.pk).update(
                review_count=F("review_count") + 1,
                average_stars=(
                    F("average_stars") * F("review_count") + review.stars
                ) / (F("review_count") + 1),
            )

            cache.delete(f"biz_detail:{business.business_id}")
            return redirect("business:business_detail", business_id=business_id)
    else:
        form = ReviewForm()

    return render(
        request,
        "create_review.html",
        {"form": form, "business": business},
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def delete_review(request, review_id: str):
    review = get_object_or_404(Review, pk=review_id, user=request.user)
    biz_id = review.business_id
    stars_removed = float(review.stars)
    review.delete()

    STAR_VAL = Value(stars_removed, output_field=FloatField())
    ONE_VAL = Value(1, output_field=FloatField())

    # Statistic Updates: Business
    Business.objects.filter(pk=biz_id).update(
        review_count=F("review_count") - 1,
        stars=Case(
            When(review_count__lte=1, then=Value(0.0)),
            default=ExpressionWrapper(
                (F("stars") * F("review_count") - STAR_VAL)
                / (F("review_count") - ONE_VAL),
                output_field=FloatField(),
            ),
        ),
    )

    # Statistic Updates: User
    User.objects.filter(pk=request.user.pk).update(
        review_count=F("review_count") - 1,
        average_stars=Case(
            When(review_count__lte=1, then=Value(0.0)),
            default=ExpressionWrapper(
                (F("average_stars") * F("review_count") - STAR_VAL)
                / (F("review_count") - ONE_VAL),
                output_field=FloatField(),
            ),
        ),
    )

    cache.delete(f"biz_detail:{biz_id}")
    return redirect("user:profile")
