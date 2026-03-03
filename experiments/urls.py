"""
URL routing for the ``experiments`` application.

Endpoints:
    ``/experiments/predict/`` — interactive review prediction demo page.
"""

from django.urls import path
from experiments.views import predict_review

app_name = 'experiments'

urlpatterns = [
    path('predict/', predict_review, name='predict_review'),
]
