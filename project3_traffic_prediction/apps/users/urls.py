"""用户管理模块 - URL配置"""
from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('list/', views.user_list_view, name='user_list'),
    path('activity/', views.activity_log_view, name='activity_log'),
]
