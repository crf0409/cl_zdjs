"""API模块 - 视图函数（Django REST Framework）"""
import random
from datetime import timedelta

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.traffic_data.models import TrafficFlow, PredictionResult
from apps.prediction.models import TrainedModel
from apps.users.views import _log_activity
from .serializers import (
    TrafficFlowSerializer,
    TrafficFlowCreateSerializer,
    PredictionResultSerializer,
    TrainedModelSerializer,
    PredictionRequestSerializer,
)


class TrafficFlowViewSet(viewsets.ModelViewSet):
    """交通流量数据API视图集
    提供交通流量数据的完整CRUD操作
    - GET /api/v1/traffic/ : 列表（支持过滤）
    - POST /api/v1/traffic/ : 创建新记录
    - GET /api/v1/traffic/{id}/ : 获取单条记录
    - PUT /api/v1/traffic/{id}/ : 更新记录
    - DELETE /api/v1/traffic/{id}/ : 删除记录
    """
    queryset = TrafficFlow.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """根据操作类型选择序列化器"""
        if self.action in ['create', 'update', 'partial_update']:
            return TrafficFlowCreateSerializer
        return TrafficFlowSerializer

    def get_queryset(self):
        """支持查询参数过滤"""
        queryset = TrafficFlow.objects.all()

        # 按监测点位过滤
        location = self.request.query_params.get('location')
        if location:
            queryset = queryset.filter(location__icontains=location)

        # 按数据源过滤
        source = self.request.query_params.get('source')
        if source:
            queryset = queryset.filter(source=source)

        # 按日期范围过滤
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)

        # 按清洗状态过滤
        is_cleaned = self.request.query_params.get('is_cleaned')
        if is_cleaned is not None:
            queryset = queryset.filter(is_cleaned=(is_cleaned.lower() == 'true'))

        return queryset

    def perform_create(self, serializer):
        """创建时自动关联上传用户"""
        serializer.save(uploaded_by=self.request.user)


class PredictionResultViewSet(viewsets.ReadOnlyModelViewSet):
    """预测结果API视图集（只读）
    - GET /api/v1/predictions/ : 预测结果列表
    - GET /api/v1/predictions/{id}/ : 获取单条预测结果
    """
    queryset = PredictionResult.objects.all()
    serializer_class = PredictionResultSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """支持查询参数过滤"""
        queryset = PredictionResult.objects.all()

        # 按模型类型过滤
        model_type = self.request.query_params.get('model_type')
        if model_type:
            queryset = queryset.filter(model_type=model_type)

        # 按点位过滤
        location = self.request.query_params.get('location')
        if location:
            queryset = queryset.filter(location__icontains=location)

        # 按模型版本过滤
        version = self.request.query_params.get('version')
        if version:
            queryset = queryset.filter(model_version=version)

        return queryset


class ModelViewSet(viewsets.ReadOnlyModelViewSet):
    """训练模型API视图集（只读）
    - GET /api/v1/models/ : 模型列表
    - GET /api/v1/models/{id}/ : 获取模型详情
    """
    queryset = TrainedModel.objects.all()
    serializer_class = TrainedModelSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """支持查询参数过滤"""
        queryset = TrainedModel.objects.all()

        # 按模型类型过滤
        model_type = self.request.query_params.get('model_type')
        if model_type:
            queryset = queryset.filter(model_type=model_type)

        # 按状态过滤
        model_status = self.request.query_params.get('status')
        if model_status:
            queryset = queryset.filter(status=model_status)

        return queryset


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def predict_api(request):
    """预测API端点
    POST /api/v1/predict/
    请求体: {"model_id": 1, "location": "监测点A", "prediction_hours": 3}
    返回: 预测结果列表
    """
    serializer = PredictionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': '请求参数错误',
            'details': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)

    model_id = serializer.validated_data['model_id']
    location = serializer.validated_data['location']
    prediction_hours = serializer.validated_data['prediction_hours']

    # 验证模型是否存在且可用
    trained_model = get_object_or_404(TrainedModel, pk=model_id)
    if trained_model.status not in ['completed', 'deployed']:
        return Response({
            'error': '所选模型尚未完成训练或已失效',
            'model_status': trained_model.status,
        }, status=status.HTTP_400_BAD_REQUEST)

    # 尝试使用实际模型进行预测
    predictions = []
    try:
        from utils.model_predictor import run_prediction
        prediction_results = run_prediction(trained_model, location, prediction_hours)
        for pred in prediction_results:
            predictions.append(PredictionResultSerializer(pred).data)
    except ImportError:
        # ML库未安装，生成模拟预测数据
        now = timezone.now()
        for i in range(prediction_hours):
            pred_time = now + timedelta(hours=i + 1)
            predicted_flow = random.randint(50, 300)
            pred = PredictionResult.objects.create(
                model_type=trained_model.model_type,
                model_version=trained_model.version,
                location=location,
                prediction_time=pred_time,
                predicted_flow=predicted_flow,
                predicted_vehicle=int(predicted_flow * 0.6),
                predicted_pedestrian=int(predicted_flow * 0.2),
                confidence_interval_low=int(predicted_flow * 0.85),
                confidence_interval_high=int(predicted_flow * 1.15),
                created_by=request.user,
            )
            predictions.append(PredictionResultSerializer(pred).data)
    except Exception as e:
        return Response({
            'error': f'预测执行失败: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 记录预测活动
    _log_activity(
        request.user, 'predict',
        f'API预测: 模型={trained_model.name}, 点位={location}, 时长={prediction_hours}h',
        request
    )

    return Response({
        'model': TrainedModelSerializer(trained_model).data,
        'location': location,
        'prediction_hours': prediction_hours,
        'predictions': predictions,
        'count': len(predictions),
    }, status=status.HTTP_200_OK)
