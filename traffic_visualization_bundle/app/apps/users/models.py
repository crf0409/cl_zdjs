"""用户管理模块 - 数据模型"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """自定义用户模型，支持多角色"""
    ROLE_CHOICES = (
        ('admin', '管理员'),
        ('user', '普通用户'),
        ('analyst', '数据分析师'),
    )
    role = models.CharField('角色', max_length=20, choices=ROLE_CHOICES, default='user')
    phone = models.CharField('手机号', max_length=15, blank=True)
    avatar = models.ImageField('头像', upload_to='avatars/', blank=True)
    department = models.CharField('部门', max_length=100, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户管理'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_analyst(self):
        return self.role == 'analyst'


class UserActivity(models.Model):
    """用户活动记录"""
    ACTION_CHOICES = (
        ('login', '登录'),
        ('logout', '登出'),
        ('upload', '上传数据'),
        ('train', '训练模型'),
        ('predict', '执行预测'),
        ('export', '导出报告'),
        ('view', '查看页面'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities', verbose_name='用户')
    action = models.CharField('操作类型', max_length=20, choices=ACTION_CHOICES)
    detail = models.TextField('操作详情', blank=True)
    ip_address = models.GenericIPAddressField('IP地址', null=True, blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '用户活动'
        verbose_name_plural = '活动记录'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.created_at}"
