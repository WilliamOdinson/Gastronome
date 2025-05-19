from django.urls import path
from api.views import predict_review_api, get_captcha_image, CreateReviewAPIView

app_name = 'api'

urlpatterns = [
    path('predict/', predict_review_api, name='predict_review_api'),
    path("captcha/", get_captcha_image, name="get_captcha"),
    path("business/<str:business_id>/review/", CreateReviewAPIView.as_view(), name="api_create_review")
]
