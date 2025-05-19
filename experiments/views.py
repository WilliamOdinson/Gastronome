from django.shortcuts import render
from django.urls import reverse
import requests


def predict_review(request):
    return render(request, 'predict.html')
