import json
import random
import time
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.captcha import generate_captcha_text
from api.inference import predict_score
from api.serializers import ReviewSerializer
from business.models import Business
from review.models import Review


@require_POST
def predict_review_api(request: HttpRequest) -> JsonResponse:
    """
    Process a JSON POST of a restaurant review and return a star-rating prediction.
    """
    try:
        payload = json.loads(request.body)
        text = payload.get('review', '').strip()
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not text:
        return JsonResponse({'error': 'Empty review'}, status=400)

    prediction = predict_score(text)
    return JsonResponse({'prediction': prediction})


def get_captcha_image(request):
    """
    Generates a CAPTCHA image containing random characters, stores the verification code in the session,
    and returns the image as a PNG HTTP response.
    """
    mode = "RGB"
    size = (200, 100)
    char_count = 4

    bg_color = tuple(random.randint(200, 255) for _ in range(3))
    image = Image.new(mode=mode, size=size, color=bg_color)
    imagedraw = ImageDraw.Draw(image)

    verify_code = generate_captcha_text(length=char_count)
    request.session["captcha_code"] = [verify_code, time.time()]

    font = ImageFont.truetype(settings.FONT_PATH, 60)
    char_width = size[0] // char_count

    for idx, char in enumerate(verify_code):
        char_color = tuple(random.randint(0, 150) for _ in range(3))

        char_image = Image.new("RGBA", (char_width, size[1]), (255, 255, 255, 0))
        char_draw = ImageDraw.Draw(char_image)
        char_draw.text((10, 10), char, font=font, fill=char_color)

        angle = random.randint(-30, 30)
        rotated = char_image.rotate(angle, expand=True)

        pos_x = idx * char_width + (char_width - rotated.width) // 2
        pos_y = (size[1] - rotated.height) // 2

        pos_x = max(0, pos_x)
        pos_y = max(0, pos_y)

        image.paste(rotated, (pos_x, pos_y), rotated)

    for _ in range(random.randint(3, 6)):
        line_color = tuple(random.randint(0, 150) for _ in range(3))
        start = (random.randint(0, size[0]), random.randint(0, size[1]))
        end = (random.randint(0, size[0]), random.randint(0, size[1]))
        imagedraw.line([start, end], fill=line_color, width=2)

    for _ in range(1000):
        dot_color = tuple(random.randint(0, 255) for _ in range(3))
        pos = (random.randint(0, size[0] - 1), random.randint(0, size[1] - 1))
        imagedraw.point(pos, fill=dot_color)

    buffer = BytesIO()
    image.save(buffer, "png")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


class CreateReviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, business_id: str):
        business = get_object_or_404(Business, pk=business_id)

        if Review.objects.filter(user=request.user, business=business).exists():
            return Response(
                {"detail": "You have already reviewed this business."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        User = get_user_model()

        with transaction.atomic():
            review = serializer.save(user=request.user, business=business)
            review.auto_score = predict_score(review.text)
            review.save(update_fields=["auto_score"])

            Business.objects.filter(pk=business.pk).update(
                review_count=F("review_count") + 1,
                stars=(
                    F("stars") * F("review_count") + review.stars
                ) / (F("review_count") + 1),
            )

            User.objects.filter(pk=request.user.pk).update(
                review_count=F("review_count") + 1
            )

        return Response(
            ReviewSerializer(review).data, status=status.HTTP_201_CREATED
        )
