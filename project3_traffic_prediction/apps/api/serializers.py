"""API模块 - 序列化器定义"""
from rest_framework import serializers
from apps.traffic_data.models import TrafficFlow, WeatherData, PredictionResult
from apps.prediction.models import TrainedModel


class TrafficFlowSerializer(serializers.ModelSerializer):
    """交通流量数据序列化器"""
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True, default='')

    class Meta:
        model = TrafficFlow
        fields = [
            'id', 'timestamp', 'location', 'camera_id',
            'vehicle_count', 'pedestrian_count', 'bicycle_count',
            'motorcycle_count', 'truck_count', 'total_flow',
            'avg_speed', 'occupancy_rate', 'source', 'source_display',
            'confidence', 'is_cleaned', 'uploaded_by', 'uploaded_by_name',
            'created_at',
        ]
        read_only_fields = ['total_flow', 'created_at']


class TrafficFlowCreateSerializer(serializers.ModelSerializer):
    """交通流量数据创建序列化器（写入用）"""

    class Meta:
        model = TrafficFlow
        fields = [
            'timestamp', 'location', 'camera_id',
            'vehicle_count', 'pedestrian_count', 'bicycle_count',
            'motorcycle_count', 'truck_count',
            'avg_speed', 'occupancy_rate', 'source', 'confidence',
        ]


class WeatherDataSerializer(serializers.ModelSerializer):
    """气象数据序列化器"""
    weather_type_display = serializers.CharField(source='get_weather_type_display', read_only=True)

    class Meta:
        model = WeatherData
        fields = [
            'id', 'timestamp', 'location', 'weather_type', 'weather_type_display',
            'temperature', 'humidity', 'wind_speed', 'visibility',
            'precipitation', 'created_at',
        ]
        read_only_fields = ['created_at']


class PredictionResultSerializer(serializers.ModelSerializer):
    """预测结果序列化器"""
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = PredictionResult
        fields = [
            'id', 'model_type', 'model_type_display', 'model_version',
            'location', 'prediction_time', 'predicted_flow', 'actual_flow',
            'predicted_vehicle', 'predicted_pedestrian',
            'mae', 'rmse', 'mape',
            'confidence_interval_low', 'confidence_interval_high',
            'created_by', 'created_by_name', 'created_at',
        ]
        read_only_fields = ['created_at']


class TrainedModelSerializer(serializers.ModelSerializer):
    """训练模型序列化器"""
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = TrainedModel
        fields = [
            'id', 'name', 'model_type', 'model_type_display',
            'version', 'status', 'status_display',
            'epochs', 'batch_size', 'learning_rate', 'sequence_length',
            'train_loss', 'val_loss', 'mae', 'rmse', 'mape', 'r2_score',
            'training_time', 'description',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class PredictionRequestSerializer(serializers.Serializer):
    """预测请求序列化器（用于API预测端点）"""
    model_id = serializers.IntegerField(help_text='模型ID')
    location = serializers.CharField(max_length=200, help_text='预测点位')
    prediction_hours = serializers.IntegerField(default=1, min_value=1, max_value=72, help_text='预测时长(小时)')
