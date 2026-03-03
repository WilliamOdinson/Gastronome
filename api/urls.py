"""
URL routing for the ``api`` application.

Endpoints:
    ``/api/predict/``   — POST a review text, receive a star-rating prediction (JSON).
    ``/api/captcha/``   — GET a dynamically generated CAPTCHA image (PNG).
"""

from django.urls import path
from api.views import predict_review_api, get_captcha_image

app_name = 'api'

urlpatterns = [
    path('predict/', predict_review_api, name='predict_review_api'),
    path("captcha/", get_captcha_image, name="get_captcha"),
]
