"""
URL routing for the ``user`` application.

Endpoints:
    ``/user/login/``                — login form (CAPTCHA-protected).
    ``/user/logout/``               — logout (POST only).
    ``/user/profile/``              — authenticated user's profile page.
    ``/user/register/``             — registration form (CAPTCHA-protected).
    ``/user/verify-email/``         — email verification code entry.
    ``/user/resend-verification/``  — resend the verification code.
"""

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
