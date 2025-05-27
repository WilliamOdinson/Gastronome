import logging

from celery import shared_task
from django.db import transaction

from api.inference import predict_score
from review.models import Review

logger = logging.getLogger(__name__)


@shared_task(queue="bert-predict")
def compute_auto_score(review_id: str) -> None:
    """
    Extract the specified review, call the BERT classifier, and asynchronously write back the auto_score.
    """
    try:
        review = Review.objects.only("pk", "text").get(pk=review_id)
    except Review.DoesNotExist:
        logger.warning("Review %s not found - skip auto-score task", review_id)
        return

    score = predict_score(review.text)

    # use update to avoid generating a new save signal
    with transaction.atomic():
        Review.objects.filter(pk=review_id).update(auto_score=score)
