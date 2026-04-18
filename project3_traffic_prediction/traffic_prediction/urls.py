"""traffic_prediction URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.visualization.views import dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard, name='home'),
    path('users/', include('apps.users.urls')),
    path('traffic/', include('apps.traffic_data.urls')),
    path('prediction/', include('apps.prediction.urls')),
    path('visualization/', include('apps.visualization.urls')),
    path('monitoring/', include('apps.monitoring.urls')),
    path('reports/', include('apps.reports.urls')),
    path('api/v1/', include('apps.api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
