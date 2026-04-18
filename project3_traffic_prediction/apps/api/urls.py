"""API模块 - URL配置（使用DRF路由器）"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'traffic', views.TrafficFlowViewSet, basename='traffic')
router.register(r'predictions', views.PredictionResultViewSet, basename='predictions')
router.register(r'models', views.ModelViewSet, basename='models')

urlpatterns = [
    path('', include(router.urls)),
    path('predict/', views.predict_api, name='api_predict'),
]
