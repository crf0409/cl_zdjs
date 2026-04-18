"""交通数据管理模块 - 后台管理配置"""
from django.contrib import admin
from .models import TrafficFlow, WeatherData, TimePeriodLabel, PredictionResult


@admin.register(TrafficFlow)
class TrafficFlowAdmin(admin.ModelAdmin):
    """交通流量数据管理后台"""
    list_display = [
        'timestamp', 'location', 'camera_id', 'total_flow',
        'vehicle_count', 'pedestrian_count', 'avg_speed',
        'source', 'is_cleaned', 'uploaded_by',
    ]
    list_filter = ['source', 'is_cleaned', 'timestamp', 'location']
    search_fields = ['location', 'camera_id']
    date_hierarchy = 'timestamp'
    readonly_fields = ['total_flow', 'created_at']
    ordering = ['-timestamp']
    list_per_page = 50


@admin.register(WeatherData)
class WeatherDataAdmin(admin.ModelAdmin):
    """气象数据管理后台"""
    list_display = [
        'timestamp', 'location', 'weather_type', 'temperature',
        'humidity', 'wind_speed', 'visibility', 'precipitation',
    ]
    list_filter = ['weather_type', 'timestamp', 'location']
    search_fields = ['location']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    list_per_page = 50


@admin.register(TimePeriodLabel)
class TimePeriodLabelAdmin(admin.ModelAdmin):
    """时段标签管理后台"""
    list_display = [
        'date', 'period', 'day_type', 'holiday_name',
        'is_event', 'event_name', 'flow_factor',
    ]
    list_filter = ['period', 'day_type', 'is_event']
    search_fields = ['holiday_name', 'event_name']
    date_hierarchy = 'date'
    ordering = ['-date']
    list_per_page = 50


@admin.register(PredictionResult)
class PredictionResultAdmin(admin.ModelAdmin):
    """预测结果管理后台"""
    list_display = [
        'model_type', 'model_version', 'location', 'prediction_time',
        'predicted_flow', 'actual_flow', 'mae', 'rmse', 'mape',
        'created_by', 'created_at',
    ]
    list_filter = ['model_type', 'prediction_time', 'location']
    search_fields = ['location', 'model_version']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    list_per_page = 50
