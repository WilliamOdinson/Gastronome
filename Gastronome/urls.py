from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import page_not_found, server_error, permission_denied, bad_request

urlpatterns = [
    path('admin/', admin.site.urls),
    path('business/', include('business.urls')),
    path('user/', include('user.urls')),
    path('api/', include('api.urls')),
    path('experiments/', include('experiments.urls')),
    path('recommend/', include('recommend.urls')),
    path('review/', include('review.urls')),
    path('', include('core.urls')),
]

handler404 = page_not_found
handler500 = server_error
handler403 = permission_denied
handler400 = bad_request

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
