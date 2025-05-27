from django.urls import path
from review.views import create_review, delete_review

app_name = 'review'

urlpatterns = [
    path("add/<str:business_id>/", create_review, name="create_review"),
    path("delete/<str:review_id>/", delete_review, name="delete_review"),
]
