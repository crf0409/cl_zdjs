"""系统监控模块 - URL配置"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.system_status_view, name='system_status'),
    path('model/', views.model_monitor_view, name='model_monitor'),
    path('data/', views.data_monitor_view, name='data_monitor'),
]
