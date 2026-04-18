"""系统监控模块 - 视图函数"""
import json
import platform
from datetime import timedelta

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Max, Min, Sum
from django.utils import timezone

from apps.traffic_data.models import TrafficFlow, PredictionResult
from apps.prediction.models import TrainedModel, TrainingLog
from apps.users.models import UserActivity


@login_required
def system_status_view(request):
    """系统状态监控视图
    展示系统运行状态，包括：CPU、内存、磁盘使用率、GPU状态等
    """
    system_info = {
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'processor': platform.processor(),
        'machine': platform.machine(),
    }

    # 尝试获取系统资源信息
    resource_info = {
        'cpu_percent': 0,
        'memory_total': 0,
        'memory_used': 0,
        'memory_percent': 0,
        'disk_total': 0,
        'disk_used': 0,
        'disk_percent': 0,
    }

    try:
        import psutil
        # CPU使用率
        resource_info['cpu_percent'] = psutil.cpu_percent(interval=1)
        resource_info['cpu_count'] = psutil.cpu_count()

        # 内存使用
        memory = psutil.virtual_memory()
        resource_info['memory_total'] = round(memory.total / (1024 ** 3), 2)  # GB
        resource_info['memory_used'] = round(memory.used / (1024 ** 3), 2)
        resource_info['memory_percent'] = memory.percent

        # 磁盘使用
        disk = psutil.disk_usage('/')
        resource_info['disk_total'] = round(disk.total / (1024 ** 3), 2)
        resource_info['disk_used'] = round(disk.used / (1024 ** 3), 2)
        resource_info['disk_percent'] = round(disk.percent, 1)
    except ImportError:
        resource_info['error'] = 'psutil库未安装，无法获取系统资源信息'

    # 尝试获取GPU信息
    gpu_info = []
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 5:
                    gpu_info.append({
                        'name': parts[0],
                        'memory_total': float(parts[1]),
                        'memory_used': float(parts[2]),
                        'utilization': float(parts[3]),
                        'temperature': float(parts[4]),
                        'memory_percent': round(float(parts[2]) / float(parts[1]) * 100, 1) if float(parts[1]) > 0 else 0,
                    })
    except Exception:
        pass  # GPU信息获取失败，不影响页面展示

    # 数据库统计
    db_stats = {
        'traffic_records': TrafficFlow.objects.count(),
        'prediction_records': PredictionResult.objects.count(),
        'model_count': TrainedModel.objects.count(),
        'activity_count': UserActivity.objects.count(),
    }

    # 最近活动日志
    recent_activities = UserActivity.objects.all()[:20]

    context = {
        'system_info': system_info,
        'resource_info': resource_info,
        'gpu_info': gpu_info,
        'db_stats': db_stats,
        'recent_activities': recent_activities,
    }
    return render(request, 'monitoring/system_status.html', context)


@login_required
def model_monitor_view(request):
    """模型性能监控视图
    跟踪已部署模型的预测精度变化，及时发现模型退化
    """
    now = timezone.now()
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # 获取所有已部署和已完成的模型
    active_models = TrainedModel.objects.filter(
        status__in=['deployed', 'completed']
    ).order_by('-created_at')

    # 每个模型的近期预测表现
    model_performance = []
    for model in active_models[:10]:
        recent_preds = PredictionResult.objects.filter(
            model_type=model.model_type,
            model_version=model.version,
            created_at__gte=last_7d,
        )

        # 有实际值的预测，用来计算误差
        evaluated_preds = recent_preds.filter(actual_flow__isnull=False)

        perf_stats = evaluated_preds.aggregate(
            avg_mae=Avg('mae'),
            avg_rmse=Avg('rmse'),
            avg_mape=Avg('mape'),
            total_predictions=Count('id'),
        )

        # 30天内的表现趋势（按周）
        weekly_perf = []
        for week in range(4):
            week_start = now - timedelta(days=7 * (week + 1))
            week_end = now - timedelta(days=7 * week)
            week_stats = PredictionResult.objects.filter(
                model_type=model.model_type,
                model_version=model.version,
                actual_flow__isnull=False,
                created_at__gte=week_start,
                created_at__lt=week_end,
            ).aggregate(avg_mape=Avg('mape'))
            weekly_perf.append({
                'week': f'第{4 - week}周',
                'mape': round(week_stats['avg_mape'] or 0, 2),
            })
        weekly_perf.reverse()

        model_performance.append({
            'model': model,
            'stats': perf_stats,
            'weekly_perf': weekly_perf,
            'total_recent': recent_preds.count(),
        })

    # 模型退化告警（MAPE超过阈值的模型）
    alert_threshold = 15.0  # MAPE超过15%视为需要关注
    alerts = []
    for mp in model_performance:
        if mp['stats']['avg_mape'] and mp['stats']['avg_mape'] > alert_threshold:
            alerts.append({
                'model': mp['model'],
                'mape': round(mp['stats']['avg_mape'], 2),
                'level': '严重' if mp['stats']['avg_mape'] > 25 else '警告',
            })

    # 图表数据
    chart_data = json.dumps({
        'model_names': [mp['model'].name for mp in model_performance],
        'mae_values': [round(mp['stats']['avg_mae'] or 0, 2) for mp in model_performance],
        'rmse_values': [round(mp['stats']['avg_rmse'] or 0, 2) for mp in model_performance],
        'mape_values': [round(mp['stats']['avg_mape'] or 0, 2) for mp in model_performance],
    })

    context = {
        'active_models': active_models,
        'model_performance': model_performance,
        'alerts': alerts,
        'alert_threshold': alert_threshold,
        'chart_data': chart_data,
    }
    return render(request, 'monitoring/model_monitor.html', context)


@login_required
def data_monitor_view(request):
    """数据质量监控视图
    监控数据采集的实时性、完整性和准确性
    """
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    # 数据采集实时性监控
    latest_record = TrafficFlow.objects.first()  # 按timestamp降序排列的第一条
    data_freshness = None
    if latest_record:
        data_freshness = (now - latest_record.timestamp).total_seconds() / 60  # 分钟

    # 最近24小时每小时数据量
    hourly_counts = []
    for i in range(24):
        hour_start = now - timedelta(hours=24 - i)
        hour_end = now - timedelta(hours=23 - i)
        count = TrafficFlow.objects.filter(
            created_at__gte=hour_start,
            created_at__lt=hour_end,
        ).count()
        hourly_counts.append({
            'hour': hour_start.strftime('%H:00'),
            'count': count,
        })

    # 数据缺失检测：检查每个监测点位是否有数据中断
    location_health = []
    active_locations = TrafficFlow.objects.filter(
        timestamp__gte=last_24h
    ).values('location').distinct()

    for loc_dict in active_locations[:20]:
        loc = loc_dict['location']
        loc_data = TrafficFlow.objects.filter(
            location=loc,
            timestamp__gte=last_24h,
        )
        loc_count = loc_data.count()
        loc_latest = loc_data.aggregate(latest=Max('timestamp'))['latest']
        gap_minutes = 0
        if loc_latest:
            gap_minutes = round((now - loc_latest).total_seconds() / 60, 1)

        # 每小时期望至少有一条数据，24小时至少24条
        health_status = '正常' if loc_count >= 12 else ('警告' if loc_count >= 6 else '异常')

        location_health.append({
            'location': loc,
            'record_count': loc_count,
            'latest_time': loc_latest,
            'gap_minutes': gap_minutes,
            'health_status': health_status,
        })

    # 异常值检测统计
    anomaly_stats = {
        'negative_values': TrafficFlow.objects.filter(
            timestamp__gte=last_7d,
            total_flow__lt=0,
        ).count(),
        'zero_flow': TrafficFlow.objects.filter(
            timestamp__gte=last_7d,
            total_flow=0,
        ).count(),
        'null_speed': TrafficFlow.objects.filter(
            timestamp__gte=last_7d,
            avg_speed__isnull=True,
        ).count(),
        'low_confidence': TrafficFlow.objects.filter(
            timestamp__gte=last_7d,
            confidence__lt=0.5,
            confidence__isnull=False,
        ).count(),
    }

    # 图表数据
    chart_data = json.dumps({
        'hourly_labels': [h['hour'] for h in hourly_counts],
        'hourly_counts': [h['count'] for h in hourly_counts],
    })

    context = {
        'data_freshness': data_freshness,
        'latest_record': latest_record,
        'hourly_counts': hourly_counts,
        'location_health': location_health,
        'anomaly_stats': anomaly_stats,
        'chart_data': chart_data,
    }
    return render(request, 'monitoring/data_monitor.html', context)
