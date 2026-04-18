"""预测模型管理模块 - URL配置"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.model_list_view, name='model_list'),
    path('train/', views.model_train_view, name='model_train'),
    path('detail/<int:pk>/', views.model_detail_view, name='model_detail'),
    path('predict/', views.predict_view, name='predict'),
    path('compare/', views.model_compare_view, name='model_compare'),
]
