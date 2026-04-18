"""报告生成模块 - URL配置"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.report_list_view, name='report_list'),
    path('generate/', views.generate_report_view, name='generate_report'),
    path('download/<str:filename>/', views.report_download_view, name='report_download'),
]
