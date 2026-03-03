"""
URL routing for the ``review`` application.

Endpoints:
    ``/review/add/<business_id>/``    — create a new review (GET form / POST submit).
    ``/review/delete/<review_id>/``   — delete the user's own review (POST only).
"""

from django.urls import path
from review.views import create_review, delete_review

app_name = 'review'

urlpatterns = [
    path("add/<str:business_id>/", create_review, name="create_review"),
    path("delete/<str:review_id>/", delete_review, name="delete_review"),
]
