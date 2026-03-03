"""
Django AppConfig for the ``api`` application.

This app exposes REST-style JSON endpoints consumed by the front-end
and external clients, including review star-rating prediction and
CAPTCHA image generation.
"""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
