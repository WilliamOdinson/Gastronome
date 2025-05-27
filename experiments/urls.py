from django.urls import path
from experiments.views import predict_review

app_name = 'experiments'

urlpatterns = [
    path('predict/', predict_review, name='predict_review'),
]
