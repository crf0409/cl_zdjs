"""可视化模块 - URL配置"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('data/', views.dashboard_data_view, name='dashboard_data'),
    path('flow-chart/', views.flow_chart_view, name='flow_chart'),
    path('heatmap/', views.heatmap_view, name='heatmap'),
    path('comparison/', views.comparison_view, name='comparison'),
    path('analysis/', views.analysis_view, name='analysis'),
]
