from django.urls import path
from . import views
from .views import create_review

app_name = 'review'

urlpatterns = [
    path("add/<str:business_id>/", create_review, name="create_review")
]
