import time
from typing import Optional

from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction

from api.inference import predict_score
from review.models import Review

logger = get_task_logger("celery.worker.bert_predict")


def _shorten(text: str, length: int = 60) -> str:
    """Return a truncated single-line preview for logging."""
    text = text.replace("\n", " ").strip()
    return text[:length] + ("..." if len(text) > length else "")


@shared_task(queue="bert_predict", bind=True)
def compute_auto_score(self, review_id: str) -> None:
    start_ts = time.perf_counter()
    logger.debug("auto-score task received review_id=%s", review_id)

    try:
        review = Review.objects.only("pk", "text").get(pk=review_id)
    except Review.DoesNotExist:
        logger.warning("review_id=%s not found - skip auto-score task", review_id)
        self.update_state(state="IGNORED", meta={"reason": "missing"})
        return
    except Exception:
        logger.exception("database error when fetching review_id=%s", review_id)
        raise

    logger.debug(
        "fetched review_id=%s preview=\"%s\"", review_id, _shorten(review.text)
    )

    try:
        score = predict_score(review.text)
    except Exception:
        logger.exception("inference failed for review_id=%s", review_id)
        raise

    logger.info(
        "prediction finished review_id=%s score=%.4f", review_id, score
    )

    try:
        with transaction.atomic():
            Review.objects.filter(pk=review_id).update(auto_score=score)
    except Exception:
        logger.exception("failed to persist auto_score for review_id=%s", review_id)
        raise
    finally:
        elapsed_ms = round((time.perf_counter() - start_ts) * 1000, 1)
        logger.debug(
            "auto-score task completed review_id=%s elapsed_ms=%.1f", review_id, elapsed_ms
        )
