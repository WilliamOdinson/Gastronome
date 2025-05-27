import random
import uuid
import secrets
import re

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.utils.crypto import get_random_string

from review.models import Review, Tip
from user.models import User
from user.tasks import send_verification_email


@csrf_protect
def user_login(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password")
        captcha_input = request.POST.get("captcha", "").upper()

        saved = request.session.pop("captcha_code", None)
        if not saved or captcha_input != saved[0].upper():
            return render(request, "login.html",
                          {"error": "Invalid captcha. Click the image to refresh."})

        user = authenticate(request, email=email, password=password)
        if user:
            login(request, user)
            return redirect("user:profile")
        return render(request, "login.html",
                      {"error": "Invalid email or password."})
    return render(request, "login.html")


@require_http_methods(["POST"])
def user_logout(request):
    """
    Log the user out and redirect to homepage.
    """
    logout(request)
    return redirect("core:index")


@login_required
def user_profile(request):
    user = request.user
    reviews = Review.objects.filter(user=user).select_related("business")
    tips = Tip.objects.filter(user=user).select_related("business")

    return render(request, "profile.html", {
        "user_obj": user,
        "reviews": reviews,
        "tips": tips,
    })


@csrf_protect
def register(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")
        display_name = request.POST.get("display_name")
        captcha_input = request.POST.get("captcha", "").upper()

        saved = request.session.pop("captcha_code", None)
        if not saved or captcha_input != saved[0].upper():
            return render(request, "register.html",
                          {"error": "Invalid captcha. Click the image to refresh."})

        if not email or not password1 or not password2 or not display_name:
            return render(request, "register.html", {"error": "All fields are required."})

        if password1 != password2:
            return render(request, "register.html", {"error": "Passwords do not match."})

        pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"
        if not re.match(pattern, password1):
            return render(request, "register.html", {
                "error": (
                    "Password must be at least 8 characters "
                    "and include upper and lower-case letters and a digit."
                )
            })

        if User.objects.filter(email__iexact=email).exists():
            return render(request, "register.html", {
                "error": "This email is already registered."
            })

        verification_code = "".join(str(secrets.randbelow(10)) for _ in range(6))
        password_hash = make_password(password1)

        cache.set(
            f"pending_register:{email}",
            {
                "password_hash": password_hash,
                "display_name": display_name,
                "verification_code": verification_code,
            },
            timeout=600,
        )

        # asynchronous e-mail; returns immediately
        send_verification_email.delay(email, verification_code)
        print(f"Verification code {verification_code} queued for {email}")

        request.session["pending_email"] = email
        return redirect("user:verify_email")
    return render(request, "register.html")


def verify_email(request):
    if request.method == "POST":
        code = request.POST.get("code")
        email = request.session.get("pending_email")

        if not email:
            return redirect("user:register")

        data = cache.get(f"pending_register:{email}")
        if not data:
            return render(request, "verify_email.html", {
                          "error": "Verification expired, please register again."})

        if data["verification_code"] == code:
            user = User.objects.create(
                email=email,
                display_name=data["display_name"],
                username=email,
                user_id=uuid.uuid4().hex[:22],
            )
            user.password = data["password_hash"]
            user.save()

            cache.delete(f"pending_register:{email}")

            login(request, user)
            return redirect('core:index')
        else:
            return render(request, "verify_email.html",
                          {"error": "Invalid verification code."})
    return render(request, "verify_email.html")


def resend_verification(request):
    email = request.session.get("pending_email")
    if not email:
        return redirect("user:register")

    data = cache.get(f"pending_register:{email}")
    if not data:
        return render(
            request,
            "verify_email.html",
            {"error": "Verification expired, please register again."},
        )

    new_code = "".join(str(secrets.randbelow(10)) for _ in range(6))
    data["verification_code"] = new_code
    cache.set(f"pending_register:{email}", data, timeout=1800)

    # asynchronous e-mail
    send_verification_email.delay(email, new_code)
    print(f"New verification code {new_code} queued for {email}")

    return redirect("user:verify_email")
