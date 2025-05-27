from django.apps import AppConfig


class RecommendConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recommend'

    def ready(self) -> None:
        """On worker boot, schedule fallback recommendation cache warm-up."""
        try:
            from celery.signals import worker_ready
            from recommend.tasks import warmup_state_hotlists
        except ImportError:
            return

        worker_ready.connect(
            lambda **_: warmup_state_hotlists.apply_async(countdown=300),
            weak=False
        )
