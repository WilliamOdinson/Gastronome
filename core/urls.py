from django.urls import path
from .views import index, system_map, tech_details, search

app_name = 'core'

urlpatterns = [
    path('', index, name='index'),
    path('system/', system_map, name='system_map'),
    path('tech/', tech_details, name='tech_details'),
    path("search/", search, name="search"),
]
