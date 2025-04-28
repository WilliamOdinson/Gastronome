from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse, JsonResponse, HttpRequest
from django.views.decorators.http import require_POST
from .inference import predict_score
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

