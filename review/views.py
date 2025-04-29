import uuid
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, get_object_or_404, render
from django.db import transaction
from django.db.models import F, Sum
from business.models import Business
from .models import Review
from .forms import ReviewForm
from api.inference import predict_score


@transaction.atomic
def create_review(request, business_id):
    if not request.user.is_authenticated:
        return redirect("login")

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

            business.review_count = F("review_count") + 1
            business.save(update_fields=["review_count"])
            business.refresh_from_db(fields=["review_count"])
            
            total_stars = Review.objects.filter(business=business).aggregate(total=Sum('stars'))['total'] or 0
            if business.review_count > 0:
                business.stars = total_stars / business.review_count
            else:
                business.stars = 0.0
            business.save(update_fields=["stars"])
            
            # Update the user's review count.
            request.user.review_count = F("review_count") + 1
            request.user.save(update_fields=["review_count"])
            request.user.refresh_from_db(fields=["review_count"])
            
            # Update the user's average stars
            user_total_stars = Review.objects.filter(user=request.user).aggregate(total=Sum('stars'))['total'] or 0
            if request.user.review_count > 0:
                request.user.average_stars = user_total_stars / request.user.review_count
            else:
                request.user.average_stars = 0.0
            request.user.save(update_fields=["average_stars"])

            return redirect("business:business_detail", business_id=business_id)
    else:
        form = ReviewForm()

    return render(request, "create_review.html", {"form": form, "business": business})
