"""预测模型管理模块 - 后台管理配置"""
from django.contrib import admin
from .models import TrainedModel, TrainingLog


@admin.register(TrainedModel)
class TrainedModelAdmin(admin.ModelAdmin):
    """训练模型管理后台"""
    list_display = [
        'name', 'model_type', 'version', 'status',
        'epochs', 'batch_size', 'learning_rate',
        'train_loss', 'val_loss', 'mae', 'rmse', 'mape', 'r2_score',
        'training_time', 'created_by', 'created_at',
    ]
    list_filter = ['model_type', 'status', 'created_at']
    search_fields = ['name', 'version', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    list_per_page = 30

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'model_type', 'version', 'status', 'file_path', 'description'),
        }),
        ('训练参数', {
            'fields': ('epochs', 'batch_size', 'learning_rate', 'sequence_length'),
        }),
        ('性能指标', {
            'fields': ('train_loss', 'val_loss', 'mae', 'rmse', 'mape', 'r2_score', 'training_time'),
        }),
        ('元数据', {
            'fields': ('created_by', 'created_at', 'updated_at'),
        }),
    )


@admin.register(TrainingLog)
class TrainingLogAdmin(admin.ModelAdmin):
    """训练日志管理后台"""
    list_display = ['model', 'epoch', 'train_loss', 'val_loss', 'learning_rate', 'timestamp']
    list_filter = ['model', 'timestamp']
    ordering = ['model', 'epoch']
    readonly_fields = ['timestamp']
    list_per_page = 50
