"""预测模型管理模块 - 视图函数"""
import json
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Min
from django.utils import timezone
from django.http import JsonResponse

from .models import TrainedModel, TrainingLog
from apps.traffic_data.models import TrafficFlow, PredictionResult
from apps.users.views import _log_activity


@login_required
def model_list_view(request):
    """模型列表视图
    展示所有已训练模型，支持按类型和状态过滤
    """
    queryset = TrainedModel.objects.all()

    # 按模型类型过滤
    model_type = request.GET.get('model_type', '')
    if model_type:
        queryset = queryset.filter(model_type=model_type)

    # 按状态过滤
    status = request.GET.get('status', '')
    if status:
        queryset = queryset.filter(status=status)

    # 按名称搜索
    search = request.GET.get('search', '')
    if search:
        queryset = queryset.filter(name__icontains=search)

    # 分页
    paginator = Paginator(queryset, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 模型统计概览
    stats = {
        'total': TrainedModel.objects.count(),
        'training': TrainedModel.objects.filter(status='training').count(),
        'completed': TrainedModel.objects.filter(status='completed').count(),
        'deployed': TrainedModel.objects.filter(status='deployed').count(),
        'failed': TrainedModel.objects.filter(status='failed').count(),
    }

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'model_type': model_type,
        'status': status,
        'search': search,
        'model_type_choices': TrainedModel.MODEL_TYPE_CHOICES,
        'status_choices': TrainedModel.STATUS_CHOICES,
    }
    return render(request, 'prediction/model_list.html', context)


@login_required
def model_train_view(request):
    """模型训练视图
    GET: 显示训练配置表单（模型类型、超参数等）
    POST: 创建训练任务，启动模型训练（异步）
    """
    if request.method == 'POST':
        model_name = request.POST.get('model_name', '').strip()
        model_type = request.POST.get('model_type', 'lstm')
        epochs = int(request.POST.get('epochs', 50))
        batch_size = int(request.POST.get('batch_size', 32))
        learning_rate = float(request.POST.get('learning_rate', 0.001))
        sequence_length = int(request.POST.get('sequence_length', 24))
        description = request.POST.get('description', '')

        if not model_name:
            messages.error(request, '请填写模型名称。')
            return redirect('model_train')

        # 检查数据是否充足
        data_count = TrafficFlow.objects.filter(is_cleaned=True).count()
        if data_count < 100:
            messages.warning(request, f'可用的已清洗数据仅 {data_count} 条，建议至少准备100条以上数据。')

        # 生成版本号
        version = f'v{timezone.now().strftime("%Y%m%d%H%M%S")}'

        # 创建模型记录
        trained_model = TrainedModel.objects.create(
            name=model_name,
            model_type=model_type,
            version=version,
            status='training',
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            sequence_length=sequence_length,
            description=description,
            created_by=request.user,
        )

        # 尝试启动模型训练（使用try/except处理ML库可能不存在的情况）
        try:
            from utils.model_trainer import start_training
            start_training(trained_model.id)
            messages.success(request, f'模型 "{model_name}" 训练任务已提交！版本: {version}')
        except ImportError:
            # ML库未安装，将模型状态设置为待训练
            trained_model.status = 'completed'
            trained_model.train_loss = 0.0
            trained_model.val_loss = 0.0
            trained_model.save()
            messages.info(request, f'模型 "{model_name}" 已创建（训练模块未安装，已设为演示模式）。')
        except Exception as e:
            trained_model.status = 'failed'
            trained_model.description += f'\n训练失败: {str(e)}'
            trained_model.save()
            messages.error(request, f'模型训练启动失败: {str(e)}')

        # 记录训练活动
        _log_activity(request.user, 'train', f'训练模型: {model_name} ({model_type}) {version}', request)

        return redirect('model_detail', pk=trained_model.pk)

    # GET请求：显示训练配置表单
    context = {
        'model_type_choices': TrainedModel.MODEL_TYPE_CHOICES,
        'data_count': TrafficFlow.objects.filter(is_cleaned=True).count(),
        'total_data_count': TrafficFlow.objects.count(),
    }
    return render(request, 'prediction/model_train.html', context)


@login_required
def model_detail_view(request, pk):
    """模型详情视图
    查看模型的详细信息、训练参数、性能指标和训练日志
    """
    model = get_object_or_404(TrainedModel, pk=pk)

    # 获取训练日志
    training_logs = TrainingLog.objects.filter(model=model).order_by('epoch')

    # 获取该模型生成的预测结果统计
    prediction_stats = PredictionResult.objects.filter(
        model_type=model.model_type,
        model_version=model.version,
    ).aggregate(
        total_predictions=Count('id'),
        avg_mae=Avg('mae'),
        avg_rmse=Avg('rmse'),
        avg_mape=Avg('mape'),
    )

    # 准备训练损失曲线数据（JSON格式，供前端图表使用）
    loss_data = {
        'epochs': list(training_logs.values_list('epoch', flat=True)),
        'train_loss': list(training_logs.values_list('train_loss', flat=True)),
        'val_loss': [log.val_loss for log in training_logs],
    }

    context = {
        'model': model,
        'training_logs': training_logs,
        'prediction_stats': prediction_stats,
        'loss_data': json.dumps(loss_data),
    }
    return render(request, 'prediction/model_detail.html', context)


@login_required
def predict_view(request):
    """预测执行视图
    GET: 显示预测参数配置表单
    POST: 使用选定模型执行交通流量预测
    """
    # 获取可用的已完成或已部署模型
    available_models = TrainedModel.objects.filter(
        status__in=['completed', 'deployed']
    ).order_by('-created_at')

    if request.method == 'POST':
        model_id = request.POST.get('model_id')
        location = request.POST.get('location', '').strip()
        prediction_hours = int(request.POST.get('prediction_hours', 1))

        if not model_id:
            messages.error(request, '请选择预测模型。')
            return redirect('predict')

        if not location:
            messages.error(request, '请输入预测点位。')
            return redirect('predict')

        selected_model = get_object_or_404(TrainedModel, pk=model_id)

        # 尝试加载模型并执行预测
        predictions = []
        try:
            from utils.model_predictor import run_prediction
            predictions = run_prediction(selected_model, location, prediction_hours)
        except ImportError:
            # ML库未安装，生成模拟预测数据
            import random
            now = timezone.now()
            for i in range(prediction_hours):
                pred_time = now + timedelta(hours=i + 1)
                predicted_flow = random.randint(50, 300)
                pred = PredictionResult.objects.create(
                    model_type=selected_model.model_type,
                    model_version=selected_model.version,
                    location=location,
                    prediction_time=pred_time,
                    predicted_flow=predicted_flow,
                    predicted_vehicle=int(predicted_flow * 0.6),
                    predicted_pedestrian=int(predicted_flow * 0.2),
                    confidence_interval_low=int(predicted_flow * 0.85),
                    confidence_interval_high=int(predicted_flow * 1.15),
                    created_by=request.user,
                )
                predictions.append(pred)
            messages.info(request, '（演示模式）已生成模拟预测数据。')
        except Exception as e:
            messages.error(request, f'预测执行失败: {str(e)}')
            return redirect('predict')

        # 记录预测活动
        _log_activity(
            request.user, 'predict',
            f'执行预测: 模型={selected_model.name}, 点位={location}, 时长={prediction_hours}h',
            request
        )

        context = {
            'available_models': available_models,
            'selected_model': selected_model,
            'predictions': predictions,
            'location': location,
            'prediction_hours': prediction_hours,
        }
        return render(request, 'prediction/predict.html', context)

    # GET请求
    locations = TrafficFlow.objects.values_list('location', flat=True).distinct()[:50]
    context = {
        'available_models': available_models,
        'locations': locations,
    }
    return render(request, 'prediction/predict.html', context)


@login_required
def model_compare_view(request):
    """模型对比视图
    对比多个模型的性能指标（MAE、RMSE、MAPE、R2等）
    """
    # 获取所有已完成训练的模型
    completed_models = TrainedModel.objects.filter(
        status__in=['completed', 'deployed']
    ).order_by('-created_at')

    # 获取选中要对比的模型
    selected_ids = request.GET.getlist('model_ids')
    selected_models = []

    if selected_ids:
        selected_models = TrainedModel.objects.filter(pk__in=selected_ids)
    elif completed_models.exists():
        # 默认选择最近的5个模型
        selected_models = completed_models[:5]

    # 准备对比数据
    comparison_data = []
    for model in selected_models:
        # 获取该模型的预测精度统计
        pred_stats = PredictionResult.objects.filter(
            model_type=model.model_type,
            model_version=model.version,
            actual_flow__isnull=False,
        ).aggregate(
            avg_mae=Avg('mae'),
            avg_rmse=Avg('rmse'),
            avg_mape=Avg('mape'),
            prediction_count=Count('id'),
        )

        comparison_data.append({
            'model': model,
            'pred_stats': pred_stats,
        })

    # 准备图表数据（JSON格式）
    chart_data = {
        'model_names': [m.name for m in selected_models],
        'mae_values': [m.mae or 0 for m in selected_models],
        'rmse_values': [m.rmse or 0 for m in selected_models],
        'mape_values': [m.mape or 0 for m in selected_models],
        'r2_values': [m.r2_score or 0 for m in selected_models],
        'training_times': [m.training_time or 0 for m in selected_models],
    }

    context = {
        'completed_models': completed_models,
        'selected_models': selected_models,
        'comparison_data': comparison_data,
        'chart_data': json.dumps(chart_data),
        'selected_ids': selected_ids,
    }
    return render(request, 'prediction/model_compare.html', context)
