import os
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Gastronome.settings")

app = Celery("Gastronome")
app.conf.worker_pool = "gevent"
app.conf.worker_concurrency = 4
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "refresh-open-status-every-5m": {
        "task": "business.tasks.refresh_open_status",
        "schedule": crontab(minute="*/5"),
    },
    "refresh-recommendation-cache-every-12h": {
        "task": "recommend.tasks.precache_recommendations",
        "schedule": crontab(minute=0, hour="*/12"),
    },
}
