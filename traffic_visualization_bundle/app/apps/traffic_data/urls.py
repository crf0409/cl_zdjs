"""交通数据管理模块 - URL配置"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.data_list_view, name='data_list'),
    path('upload/', views.data_upload_view, name='data_upload'),
    path('detail/<int:pk>/', views.data_detail_view, name='data_detail'),
    path('clean/', views.data_clean_view, name='data_clean'),
    path('quality/', views.data_quality_view, name='data_quality'),
]
