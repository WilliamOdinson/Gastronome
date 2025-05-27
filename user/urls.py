from django.urls import path
from user.views import user_login, user_logout, user_profile, register, verify_email, resend_verification

app_name = 'user'

urlpatterns = [
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),
    path('profile/', user_profile, name='profile'),
    path('register/', register, name='register'),
    path('verify-email/', verify_email, name='verify_email'),
    path('resend-verification/', resend_verification, name='resend_verification'),
]
