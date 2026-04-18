"""用户管理模块 - 后台管理配置"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserActivity


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """自定义用户管理后台"""
    list_display = ['username', 'email', 'role', 'phone', 'department', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'created_at']
    search_fields = ['username', 'email', 'phone', 'department']
    ordering = ['-created_at']

    # 在默认UserAdmin字段集的基础上添加自定义字段
    fieldsets = BaseUserAdmin.fieldsets + (
        ('扩展信息', {
            'fields': ('role', 'phone', 'avatar', 'department'),
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('扩展信息', {
            'fields': ('role', 'phone', 'department'),
        }),
    )


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    """用户活动记录管理后台"""
    list_display = ['user', 'action', 'detail', 'ip_address', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['user__username', 'detail', 'ip_address']
    readonly_fields = ['user', 'action', 'detail', 'ip_address', 'created_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        """活动记录不允许手动添加"""
        return False
