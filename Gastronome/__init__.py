"""
Gastronome — Django project package initializer.

Exposes the Celery application instance so that it is automatically
discovered when Django starts. This ensures the ``@shared_task``
decorators throughout the project are properly registered.
"""

from Gastronome.celery import app as celery_app

__all__ = ('celery_app',)
