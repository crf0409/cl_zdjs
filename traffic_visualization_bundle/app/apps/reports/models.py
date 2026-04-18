"""报告生成模块 - 数据模型"""
from django.db import models
from django.conf import settings


class Report(models.Model):
    """生成的报告记录"""
    TYPE_CHOICES = (
        ('prediction', '预测报告'),
        ('analysis', '数据分析报告'),
        ('model_eval', '模型评估报告'),
        ('summary', '综合报告'),
    )
    FORMAT_CHOICES = (
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('word', 'Word'),
    )
    title = models.CharField('报告标题', max_length=200)
    report_type = models.CharField('报告类型', max_length=20, choices=TYPE_CHOICES)
    format = models.CharField('文件格式', max_length=10, choices=FORMAT_CHOICES)
    file_path = models.FileField('报告文件', upload_to='reports/')
    description = models.TextField('报告描述', blank=True)
    date_from = models.DateField('起始日期', null=True, blank=True)
    date_to = models.DateField('结束日期', null=True, blank=True)
    file_size = models.IntegerField('文件大小(bytes)', default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, verbose_name='创建者')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '报告'
        verbose_name_plural = '报告管理'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_format_display()})"
