from django.urls import path
from business.views import business_detail

app_name = 'business'

urlpatterns = [
    path('<str:business_id>/', business_detail, name='business_detail'),
]
