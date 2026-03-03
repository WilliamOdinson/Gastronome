"""
View functions for the ``experiments`` application.

Renders the prediction demo page, which lets visitors enter free-text
review content and receive an AI-predicted star rating from the
DistilBERT classifier via an AJAX call to ``/api/predict/``.
"""

from django.shortcuts import render
from django.urls import reverse
import requests


def predict_review(request):
    return render(request, 'predict.html')
