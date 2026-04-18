"""预测模型管理模块 - 数据模型"""
from django.db import models
from django.conf import settings


class TrainedModel(models.Model):
    """已训练模型记录"""
    MODEL_TYPE_CHOICES = (
        ('lstm', 'LSTM模型'),
        ('cnn', 'CNN模型'),
        ('lstm_cnn', 'LSTM+CNN混合模型'),
        ('collaborative', '协同过滤'),
    )
    STATUS_CHOICES = (
        ('training', '训练中'),
        ('completed', '已完成'),
        ('failed', '训练失败'),
        ('deployed', '已部署'),
    )
    name = models.CharField('模型名称', max_length=100)
    model_type = models.CharField('模型类型', max_length=20, choices=MODEL_TYPE_CHOICES)
    version = models.CharField('版本号', max_length=50)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='training')
    file_path = models.FileField('模型文件', upload_to='models/', blank=True)
    # Training params
    epochs = models.IntegerField('训练轮次', default=50)
    batch_size = models.IntegerField('批次大小', default=32)
    learning_rate = models.FloatField('学习率', default=0.001)
    sequence_length = models.IntegerField('序列长度', default=24)
    # Performance metrics
    train_loss = models.FloatField('训练损失', null=True, blank=True)
    val_loss = models.FloatField('验证损失', null=True, blank=True)
    mae = models.FloatField('MAE', null=True, blank=True)
    rmse = models.FloatField('RMSE', null=True, blank=True)
    mape = models.FloatField('MAPE(%)', null=True, blank=True)
    r2_score = models.FloatField('R²', null=True, blank=True)
    training_time = models.FloatField('训练耗时(秒)', null=True, blank=True)
    # Meta
    description = models.TextField('模型描述', blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, verbose_name='创建者')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '训练模型'
        verbose_name_plural = '模型管理'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_model_type_display()}) v{self.version}"


class TrainingLog(models.Model):
    """模型训练日志"""
    model = models.ForeignKey(TrainedModel, on_delete=models.CASCADE, related_name='logs')
    epoch = models.IntegerField('轮次')
    train_loss = models.FloatField('训练损失')
    val_loss = models.FloatField('验证损失', null=True, blank=True)
    learning_rate = models.FloatField('当前学习率')
    timestamp = models.DateTimeField('记录时间', auto_now_add=True)

    class Meta:
        verbose_name = '训练日志'
        verbose_name_plural = '训练日志'
        ordering = ['epoch']
