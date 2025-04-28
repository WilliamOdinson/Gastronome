from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    path('predict/', predict_review_api, name='predict_review_api'),
]
