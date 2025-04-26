from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def home(request):
    return HttpResponse("Welcome to Gastronome!")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('business/', include('business.urls')),
    path('user/', include('user.urls')),
    path('api/', include('api.urls')),
    path('experiments/', include('experiments.urls')),
    path('recommend/', include('recommend.urls')),
    path('review/', include('review.urls')),
    path('', home, name='home'),
]
