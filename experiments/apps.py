"""
Django AppConfig for the ``experiments`` application.

Provides an interactive demo page where users can type a restaurant
review and see the DistilBERT model's predicted star rating in real time
via the ``/api/predict/`` endpoint.
"""

from django.apps import AppConfig


class ExperimentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'experiments'
