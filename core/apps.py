"""
Django AppConfig for the ``core`` application.

The core app provides site-wide functionality: the homepage, search page,
system architecture diagram, tech details page, custom error handlers,
and shared template context processors.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
