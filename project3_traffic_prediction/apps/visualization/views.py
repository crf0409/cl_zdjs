"""可视化模块 - 视图函数"""
import json
import os
import platform
import subprocess
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Sum, Count, Max, Min
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone

from apps.traffic_data.models import TrafficFlow, WeatherData, PredictionResult
from apps.prediction.models import TrainedModel
from apps.traffic_data.models import TimePeriodLabel
from apps.users.models import UserActivity, User


MENU_ITEMS = [
    {'id': 'dashboard', 'name': '数据可视化大屏', 'icon': 'bi bi-display'},
    {'id': 'data_manage', 'name': '交通数据管理', 'icon': 'bi bi-database-check'},
    {'id': 'model_manage', 'name': '预测模型管理', 'icon': 'bi bi-diagram-3'},
    {'id': 'predict_result', 'name': '预测结果展示', 'icon': 'bi bi-graph-up'},
    {'id': 'user_manage', 'name': '用户管理权限', 'icon': 'bi bi-people'},
    {'id': 'sys_monitor', 'name': '系统运行监控', 'icon': 'bi bi-activity'},
    {'id': 'api_service', 'name': 'API接口服务', 'icon': 'bi bi-cloud-arrow-down'},
    {'id': 'report_gen', 'name': '研判报告生成', 'icon': 'bi bi-file-earmark-pdf'},
]

MODEL_LABELS = dict(TrainedModel.MODEL_TYPE_CHOICES)
WEATHER_LABELS = dict(WeatherData.WEATHER_CHOICES)
ROLE_LABELS = dict(User.ROLE_CHOICES)
REPORT_DIR = os.path.join(settings.MEDIA_ROOT, 'reports')


def _safe_round(value, digits=2, default=0):
    return round(value, digits) if value is not None else default


def _format_datetime(value, fmt='%Y-%m-%d %H:%M'):
    return value.strftime(fmt) if value else '-'


def _detect_period(hour):
    if 7 <= hour < 9:
        return 'morning_peak'
    if 17 <= hour < 19:
        return 'evening_peak'
    if 9 <= hour < 17:
        return 'daytime'
    return 'night'


def _get_reference_timestamp():
    candidates = []
    latest_traffic = TrafficFlow.objects.order_by('-timestamp').first()
    latest_weather = WeatherData.objects.order_by('-timestamp').first()
    latest_prediction = PredictionResult.objects.order_by('-prediction_time').first()

    if latest_traffic:
        candidates.append(latest_traffic.timestamp)
    if latest_weather:
        candidates.append(latest_weather.timestamp)
    if latest_prediction:
        candidates.append(latest_prediction.prediction_time)

    return max(candidates) if candidates else timezone.now()


def _get_interval_minutes():
    timestamps = list(
        TrafficFlow.objects.order_by('-timestamp')
        .values_list('timestamp', flat=True)
        .distinct()[:2]
    )
    if len(timestamps) >= 2:
        interval = abs((timestamps[0] - timestamps[1]).total_seconds() / 60)
        return int(interval) if interval else 60
    return 60


def _select_focus_location():
    prediction_locations = list(
        PredictionResult.objects.order_by()
        .values_list('location', flat=True)
        .distinct()
    )
    if 'CAM_FRONT_主干道A' in prediction_locations:
        return 'CAM_FRONT_主干道A'
    if prediction_locations:
        top_location = (
            TrafficFlow.objects.filter(location__in=prediction_locations)
            .values('location')
            .annotate(total_flow=Sum('total_flow'))
            .order_by('-total_flow')
            .first()
        )
        if top_location:
            return top_location['location']
        return prediction_locations[0]

    latest_location = TrafficFlow.objects.order_by('-timestamp').values_list('location', flat=True).first()
    return latest_location or '暂无点位'


def _build_chart_payload(focus_location):
    prediction_times = list(
        PredictionResult.objects.filter(location=focus_location)
        .order_by('-prediction_time')
        .values_list('prediction_time', flat=True)
        .distinct()[:24]
    )
    prediction_times = sorted(prediction_times)

    rows = PredictionResult.objects.filter(
        location=focus_location,
        prediction_time__in=prediction_times,
    ).order_by('prediction_time', 'model_type')

    model_order = ['lstm_cnn', 'lstm', 'cnn', 'collaborative']
    grouped = {
        pred_time: {'actual': None, 'models': {}}
        for pred_time in prediction_times
    }
    available_model_types = []
    for row in rows:
        item = grouped[row.prediction_time]
        if item['actual'] is None and row.actual_flow is not None:
            item['actual'] = row.actual_flow
        item['models'][row.model_type] = row.predicted_flow
        if row.model_type not in available_model_types:
            available_model_types.append(row.model_type)

    available_model_types.sort(
        key=lambda model_type: model_order.index(model_type)
        if model_type in model_order else len(model_order)
    )

    labels = [_format_datetime(pred_time, '%m-%d %H:%M') for pred_time in prediction_times]
    actual = [grouped[pred_time]['actual'] or 0 for pred_time in prediction_times]
    series = []
    for model_type in available_model_types:
        series.append({
            'key': model_type,
            'name': MODEL_LABELS.get(model_type, model_type),
            'data': [grouped[pred_time]['models'].get(model_type, None) for pred_time in prediction_times],
        })

    return {
        'location': focus_location,
        'labels': labels,
        'actual': actual,
        'series': series,
        'title': f'{focus_location} 最近24个预测时段对比',
    }


def _build_prediction_rows(queryset):
    queryset = list(queryset)
    location_baseline = {
        item['location']: item['avg_flow'] or 0
        for item in TrafficFlow.objects.filter(
            location__in={row.location for row in queryset}
        ).values('location').annotate(avg_flow=Avg('total_flow'))
    }

    rows = []
    for row in queryset:
        baseline = location_baseline.get(row.location) or 0
        reference_flow = row.actual_flow if row.actual_flow is not None else row.predicted_flow
        status = '拥堵' if baseline and reference_flow >= baseline * 1.1 else '畅通'
        if row.actual_flow is not None:
            error_delta = row.predicted_flow - row.actual_flow
            error_text = f"{error_delta:+d}"
        else:
            error_text = '待回填'

        confidence_margin = None
        if row.confidence_interval_low is not None and row.confidence_interval_high is not None:
            confidence_margin = _safe_round(
                (row.confidence_interval_high - row.confidence_interval_low) / 2, 1
            )

        rows.append({
            'id': row.id,
            'station': row.location,
            'time': _format_datetime(row.prediction_time),
            'actual': row.actual_flow if row.actual_flow is not None else '-',
            'predict': row.predicted_flow,
            'model': MODEL_LABELS.get(row.model_type, row.model_type),
            'model_type': row.model_type,
            'confidence': confidence_margin if confidence_margin is not None else '-',
            'status': status,
            'error': error_text,
            'detail_url': (
                f"{reverse('comparison')}?{urlencode({'location': row.location, 'model_type': row.model_type})}"
            ),
        })
    return rows


def _get_report_rows():
    reports = []
    if not os.path.exists(REPORT_DIR):
        return reports

    for filename in sorted(os.listdir(REPORT_DIR), reverse=True)[:10]:
        filepath = os.path.join(REPORT_DIR, filename)
        if not os.path.isfile(filepath):
            continue
        file_stat = os.stat(filepath)
        reports.append({
            'filename': filename,
            'size_kb': round(file_stat.st_size / 1024, 1),
            'created_time': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
            'file_type': filename.rsplit('.', 1)[-1].upper() if '.' in filename else '未知',
            'download_url': reverse('report_download', args=[filename]),
        })
    return reports


def _get_resource_info():
    resource_info = {
        'cpu_percent': 0,
        'cpu_count': None,
        'memory_total': 0,
        'memory_used': 0,
        'memory_percent': 0,
        'disk_total': 0,
        'disk_used': 0,
        'disk_percent': 0,
        'gpu': [],
    }

    try:
        import psutil

        resource_info['cpu_percent'] = _safe_round(psutil.cpu_percent(interval=0.2), 1)
        resource_info['cpu_count'] = psutil.cpu_count()

        memory = psutil.virtual_memory()
        resource_info['memory_total'] = _safe_round(memory.total / (1024 ** 3), 2)
        resource_info['memory_used'] = _safe_round(memory.used / (1024 ** 3), 2)
        resource_info['memory_percent'] = _safe_round(memory.percent, 1)

        disk = psutil.disk_usage('/')
        resource_info['disk_total'] = _safe_round(disk.total / (1024 ** 3), 2)
        resource_info['disk_used'] = _safe_round(disk.used / (1024 ** 3), 2)
        resource_info['disk_percent'] = _safe_round(disk.percent, 1)
    except Exception:
        pass

    try:
        result = subprocess.run(
            [
                'nvidia-smi',
                '--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu',
                '--format=csv,noheader,nounits',
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                name, memory_total, memory_used, utilization, temperature = [
                    item.strip() for item in line.split(',')
                ]
                total_memory = float(memory_total) if memory_total else 0
                used_memory = float(memory_used) if memory_used else 0
                resource_info['gpu'].append({
                    'name': name,
                    'memory_total': total_memory,
                    'memory_used': used_memory,
                    'utilization': float(utilization) if utilization else 0,
                    'temperature': float(temperature) if temperature else 0,
                    'memory_percent': _safe_round((used_memory / total_memory) * 100, 1) if total_memory else 0,
                })
    except Exception:
        pass

    return resource_info


def _build_dashboard_payload(request):
    reference_ts = _get_reference_timestamp()
    latest_traffic = TrafficFlow.objects.order_by('-timestamp').first()
    latest_weather = WeatherData.objects.filter(timestamp__lte=reference_ts).order_by('-timestamp').first()
    latest_prediction = PredictionResult.objects.order_by('-prediction_time').first()
    snapshot_date = latest_traffic.timestamp.date() if latest_traffic else reference_ts.date()
    previous_date = snapshot_date - timedelta(days=1)

    today_stats = TrafficFlow.objects.filter(timestamp__date=snapshot_date).aggregate(
        total_flow=Sum('total_flow'),
        avg_flow=Avg('total_flow'),
        max_flow=Max('total_flow'),
        avg_speed=Avg('avg_speed'),
        total_vehicles=Sum('vehicle_count'),
        total_pedestrians=Sum('pedestrian_count'),
        record_count=Count('id'),
    )
    previous_stats = TrafficFlow.objects.filter(timestamp__date=previous_date).aggregate(
        total_flow=Sum('total_flow'),
    )
    flow_change = 0
    if previous_stats['total_flow'] and today_stats['total_flow']:
        flow_change = _safe_round(
            (today_stats['total_flow'] - previous_stats['total_flow']) / previous_stats['total_flow'] * 100, 1
        )

    interval_minutes = _get_interval_minutes()
    live_flow_raw = 0
    active_locations = 0
    if latest_traffic:
        live_snapshot = TrafficFlow.objects.filter(timestamp=latest_traffic.timestamp)
        live_flow_raw = live_snapshot.aggregate(total=Sum('total_flow'))['total'] or 0
        active_locations = live_snapshot.values('location').distinct().count()

    total_locations = TrafficFlow.objects.values('location').distinct().count()
    live_flow_hourly = int(round(live_flow_raw * 60 / max(interval_minutes, 1)))

    current_model = (
        TrainedModel.objects.filter(status='deployed')
        .order_by('rmse', '-updated_at')
        .first()
        or TrainedModel.objects.order_by('rmse', '-updated_at').first()
    )

    focus_location = _select_focus_location()
    chart_payload = _build_chart_payload(focus_location)

    period_label = TimePeriodLabel.objects.filter(
        date=snapshot_date,
        period=_detect_period(reference_ts.hour),
    ).first() or TimePeriodLabel.objects.filter(date=snapshot_date).first()

    recent_prediction_qs = PredictionResult.objects.order_by('-prediction_time', '-created_at')[:8]
    latest_prediction_rows = _build_prediction_rows(recent_prediction_qs)

    datasets = [
        {
            'name': 'traffic_data_trafficflow',
            'desc': '交通基础流量数据（真实采集）',
            'count': TrafficFlow.objects.count(),
            'update_time': _format_datetime(latest_traffic.timestamp if latest_traffic else None),
            'preview_url': reverse('data_list'),
            'manage_url': reverse('data_upload'),
        },
        {
            'name': 'traffic_data_weatherdata',
            'desc': '气象关联数据表',
            'count': WeatherData.objects.count(),
            'update_time': _format_datetime(latest_weather.timestamp if latest_weather else None),
            'preview_url': reverse('data_list'),
            'manage_url': reverse('data_clean'),
        },
        {
            'name': 'traffic_data_timeperiodlabel',
            'desc': '节假日与时段标签表',
            'count': TimePeriodLabel.objects.count(),
            'update_time': snapshot_date.strftime('%Y-%m-%d') if period_label else '-',
            'preview_url': reverse('data_quality'),
            'manage_url': reverse('data_clean'),
        },
        {
            'name': 'traffic_data_predictionresult',
            'desc': '模型预测结果存储表',
            'count': PredictionResult.objects.count(),
            'update_time': _format_datetime(latest_prediction.prediction_time if latest_prediction else None),
            'preview_url': reverse('comparison'),
            'manage_url': reverse('predict'),
        },
    ]

    model_desc_map = {
        'lstm': '使用时序特征进行交通流量预测',
        'cnn': '提取空间纹理与流量局部模式',
        'lstm_cnn': '融合时间依赖与空间特征的主力模型',
        'collaborative': '基于相似场景做趋势补充与推荐',
    }
    framework_map = {
        'lstm': 'PyTorch',
        'cnn': 'PyTorch',
        'lstm_cnn': 'PyTorch',
        'collaborative': 'Collaborative Filtering',
    }
    status_class_map = {
        'deployed': 'success',
        'completed': 'secondary',
        'training': 'info',
        'failed': 'danger',
    }
    color_class_map = {
        'lstm': 'bg-primary bg-opacity-10 text-primary',
        'cnn': 'bg-info bg-opacity-10 text-info',
        'lstm_cnn': 'bg-success bg-opacity-10 text-success',
        'collaborative': 'bg-warning bg-opacity-10 text-warning',
    }
    models = []
    for model in TrainedModel.objects.order_by('-created_at'):
        models.append({
            'id': model.id,
            'name': model.name,
            'desc': model.description or model_desc_map.get(model.model_type, ''),
            'framework': framework_map.get(model.model_type, '未知'),
            'version': model.version,
            'rmse': _safe_round(model.rmse, 2, '-'),
            'mape': _safe_round(model.mape, 2, '-'),
            'epochs': model.epochs,
            'learning_rate': model.learning_rate,
            'sequence_length': model.sequence_length,
            'status': model.get_status_display(),
            'status_key': model.status,
            'status_class': status_class_map.get(model.status, 'secondary'),
            'color': color_class_map.get(model.model_type, 'bg-secondary bg-opacity-10 text-secondary'),
            'detail_url': reverse('model_detail', args=[model.id]),
            'train_url': reverse('model_train'),
        })

    prediction_dates = [
        date_value.isoformat() for date_value in PredictionResult.objects.dates('prediction_time', 'day', order='DESC')
    ]
    selected_prediction_date = request.GET.get('prediction_date') or (prediction_dates[0] if prediction_dates else '')
    selected_prediction_location = request.GET.get('prediction_location', '')
    selected_prediction_model = request.GET.get('prediction_model', '')

    filtered_predictions = PredictionResult.objects.all()
    if selected_prediction_date:
        filtered_predictions = filtered_predictions.filter(prediction_time__date=selected_prediction_date)
    if selected_prediction_location:
        filtered_predictions = filtered_predictions.filter(location=selected_prediction_location)
    if selected_prediction_model:
        filtered_predictions = filtered_predictions.filter(model_type=selected_prediction_model)
    filtered_predictions = filtered_predictions.order_by('-prediction_time', '-created_at')

    prediction_summary = filtered_predictions.aggregate(
        total_count=Count('id'),
        avg_mae=Avg('mae'),
        avg_rmse=Avg('rmse'),
        avg_mape=Avg('mape'),
    )
    prediction_rows = []
    for row in filtered_predictions[:20]:
        detail_url = f"{reverse('comparison')}?{urlencode({'location': row.location, 'model_type': row.model_type})}"
        error_delta = None
        if row.actual_flow is not None:
            error_delta = row.predicted_flow - row.actual_flow
        prediction_rows.append({
            'id': row.id,
            'time': _format_datetime(row.prediction_time, '%H:%M'),
            'location': row.location,
            'model': MODEL_LABELS.get(row.model_type, row.model_type),
            'predicted': row.predicted_flow,
            'actual': row.actual_flow if row.actual_flow is not None else '-',
            'error': f"{error_delta:+d}" if error_delta is not None else '待回填',
            'detail_url': detail_url,
            'error_class': 'text-danger' if error_delta and error_delta > 0 else 'text-success',
        })

    role_color_map = {
        'admin': 'bg-danger',
        'analyst': 'bg-primary',
        'user': 'bg-secondary',
    }
    users = []
    for user in User.objects.order_by('-last_login', '-created_at'):
        users.append({
            'name': user.username,
            'role': ROLE_LABELS.get(user.role, user.role),
            'role_color': role_color_map.get(user.role, 'bg-secondary'),
            'last_login': _format_datetime(user.last_login) if user.last_login else '从未登录',
            'status': user.is_active,
            'profile_url': reverse('profile') if request.user.is_authenticated and request.user.pk == user.pk else reverse('user_list'),
        })

    resource_info = _get_resource_info()
    recent_activities = UserActivity.objects.select_related('user').all()[:12]
    system_logs = [
        {
            'time': _format_datetime(activity.created_at, '%Y-%m-%d %H:%M:%S'),
            'level': 'INFO' if activity.action in {'login', 'view', 'predict'} else 'WARN',
            'message': activity.detail or f'{activity.user.username} 执行了 {activity.get_action_display()}',
        }
        for activity in recent_activities
    ]

    api_base = request.build_absolute_uri('/api/v1/')
    api_list = [
        {
            'method': 'GET',
            'endpoint': '/api/v1/traffic/',
            'desc': '查询交通流量原始数据，支持 location/source/date_from/date_to 等过滤参数。',
        },
        {
            'method': 'POST',
            'endpoint': '/api/v1/traffic/',
            'desc': '写入新的交通流量记录，自动关联当前登录用户。',
        },
        {
            'method': 'GET',
            'endpoint': '/api/v1/predictions/',
            'desc': '读取已有预测结果，可按模型、点位、版本过滤。',
        },
        {
            'method': 'GET',
            'endpoint': '/api/v1/models/',
            'desc': '读取训练完成或已部署的模型清单。',
        },
        {
            'method': 'POST',
            'endpoint': '/api/v1/predict/',
            'desc': '调用指定模型执行预测并回写 PredictionResult。',
        },
    ]

    current_user = {
        'name': request.user.username if request.user.is_authenticated else '游客',
        'role': ROLE_LABELS.get(getattr(request.user, 'role', 'user'), '未登录')
        if request.user.is_authenticated else '未登录',
        'is_authenticated': request.user.is_authenticated,
        'profile_url': reverse('profile') if request.user.is_authenticated else reverse('login'),
        'logout_url': reverse('logout') if request.user.is_authenticated else reverse('login'),
    }

    report_rows = _get_report_rows()
    initial_module = request.GET.get('module', 'dashboard')
    valid_module_ids = {item['id'] for item in MENU_ITEMS}
    if initial_module not in valid_module_ids:
        initial_module = 'dashboard'

    model_health = []
    health_status_map = {
        'deployed': ('Active', 100, 'success'),
        'completed': ('Ready', 100, 'info'),
        'training': ('Training', 65, 'warning'),
        'failed': ('Offline', 20, 'danger'),
    }
    for model_type in ['lstm', 'cnn', 'lstm_cnn', 'collaborative']:
        model = TrainedModel.objects.filter(model_type=model_type).order_by('-created_at').first()
        if not model:
            continue
        label, progress, variant = health_status_map.get(model.status, ('Idle', 0, 'secondary'))
        model_health.append({
            'name': MODEL_LABELS.get(model_type, model_type),
            'status_label': label,
            'status_variant': variant,
            'progress': progress,
            'meta': f"版本 {model.version} / RMSE {_safe_round(model.rmse, 2)}",
        })

    return {
        'menu_items': MENU_ITEMS,
        'initial_module': initial_module,
        'snapshot_label': _format_datetime(reference_ts),
        'current_user': current_user,
        'summary': {
            'live_traffic_hourly': live_flow_hourly,
            'live_traffic_raw': live_flow_raw,
            'interval_minutes': interval_minutes,
            'current_model_rmse': _safe_round(current_model.rmse, 2) if current_model and current_model.rmse is not None else '-',
            'current_model_name': current_model.name if current_model else '暂无模型',
            'active_locations': active_locations,
            'total_locations': total_locations,
            'prediction_count': PredictionResult.objects.count(),
            'flow_change': flow_change,
            'service_status': 'PyTorch 推理服务运行中' if current_model else '模型尚未就绪',
            'sample_date': snapshot_date.strftime('%Y-%m-%d'),
        },
        'dashboard': {
            'chart': chart_payload,
            'weather': {
                'location': latest_weather.location if latest_weather else '暂无天气数据',
                'temperature': f"{_safe_round(latest_weather.temperature, 1)}°C" if latest_weather else '-',
                'weather_type': WEATHER_LABELS.get(latest_weather.weather_type, latest_weather.weather_type) if latest_weather else '-',
                'humidity': f"{_safe_round(latest_weather.humidity, 1)}%" if latest_weather else '-',
                'wind_speed': f"{_safe_round(latest_weather.wind_speed, 1)} m/s" if latest_weather else '-',
                'visibility': f"{_safe_round(latest_weather.visibility, 1)} km" if latest_weather else '-',
                'precipitation': f"{_safe_round(latest_weather.precipitation, 1)} mm" if latest_weather else '-',
            },
            'period': {
                'period_label': period_label.get_period_display() if period_label else '暂无标签',
                'day_type': period_label.get_day_type_display() if period_label else '-',
                'flow_factor': f"{_safe_round(period_label.flow_factor, 2)}x" if period_label else '-',
                'holiday_name': period_label.holiday_name or '无' if period_label else '无',
                'is_event': period_label.is_event if period_label else False,
                'event_name': period_label.event_name or '无' if period_label else '无',
            },
            'model_health': model_health,
            'fusion_metric': {
                'label': '主模型 MAPE',
                'value': f"{_safe_round(current_model.mape, 2)}%" if current_model and current_model.mape is not None else '-',
                'sub_label': current_model.name if current_model else '暂无主模型',
            },
            'latest_predictions': latest_prediction_rows,
        },
        'data_manage': {
            'datasets': datasets,
            'import_url': reverse('data_upload'),
            'clean_url': reverse('data_clean'),
        },
        'model_manage': {
            'models': models,
        },
        'predict_result': {
            'filters': {
                'date': selected_prediction_date,
                'location': selected_prediction_location,
                'model': selected_prediction_model,
            },
            'date_options': prediction_dates,
            'location_options': list(
                PredictionResult.objects.order_by()
                .values_list('location', flat=True)
                .distinct()
            ),
            'model_options': [
                {'value': value, 'label': label}
                for value, label in PredictionResult.MODEL_CHOICES
            ],
            'summary': {
                'total_count': prediction_summary['total_count'] or 0,
                'avg_mae': _safe_round(prediction_summary['avg_mae'], 2),
                'avg_rmse': _safe_round(prediction_summary['avg_rmse'], 2),
                'avg_mape': _safe_round(prediction_summary['avg_mape'], 2),
            },
            'rows': prediction_rows,
        },
        'user_manage': {
            'users': users,
            'register_url': reverse('register'),
        },
        'sys_monitor': {
            'system_info': {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'processor': platform.processor() or '-',
                'machine': platform.machine(),
            },
            'resources': resource_info,
            'logs': system_logs,
            'db_stats': {
                'traffic_records': TrafficFlow.objects.count(),
                'prediction_records': PredictionResult.objects.count(),
                'model_count': TrainedModel.objects.count(),
                'activity_count': UserActivity.objects.count(),
            },
        },
        'api_service': {
            'base_url': api_base,
            'auth_note': '当前接口要求登录态认证，未配置独立 API Key 管理表。',
            'endpoints': api_list,
        },
        'report_gen': {
            'generate_url': reverse('generate_report'),
            'report_list_url': reverse('report_list'),
            'reports': report_rows,
        },
    }


def dashboard(request):
    payload = _build_dashboard_payload(request)
    context = {
        'dashboard_payload': payload,
        'dashboard_data_url': reverse('dashboard_data'),
    }
    return render(request, 'visualization/dashboard.html', context)


def dashboard_data_view(request):
    payload = _build_dashboard_payload(request)
    return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})


@login_required
def flow_chart_view(request):
    """交通流量时序图视图
    展示选定时间范围和监测点位的流量变化曲线
    支持按小时/天/周进行数据聚合
    """
    # 获取过滤参数
    location = request.GET.get('location', '')
    time_range = request.GET.get('time_range', '24h')  # 24h, 7d, 30d
    granularity = request.GET.get('granularity', 'hour')  # hour, day

    now = timezone.now()

    # 确定时间范围
    if time_range == '7d':
        start_time = now - timedelta(days=7)
    elif time_range == '30d':
        start_time = now - timedelta(days=30)
    else:
        start_time = now - timedelta(hours=24)

    # 查询数据
    queryset = TrafficFlow.objects.filter(timestamp__gte=start_time)
    if location:
        queryset = queryset.filter(location=location)

    # 按粒度聚合数据
    flow_data = []
    if granularity == 'day':
        # 按天聚合
        days = (now - start_time).days + 1
        for i in range(days):
            day = (start_time + timedelta(days=i)).date()
            day_stats = queryset.filter(timestamp__date=day).aggregate(
                total=Sum('total_flow'),
                avg=Avg('total_flow'),
                vehicles=Sum('vehicle_count'),
                pedestrians=Sum('pedestrian_count'),
                avg_speed=Avg('avg_speed'),
            )
            flow_data.append({
                'time': day.strftime('%m-%d'),
                'total': day_stats['total'] or 0,
                'avg': round(day_stats['avg'] or 0, 1),
                'vehicles': day_stats['vehicles'] or 0,
                'pedestrians': day_stats['pedestrians'] or 0,
                'avg_speed': round(day_stats['avg_speed'] or 0, 1),
            })
    else:
        # 按小时聚合
        hours = int((now - start_time).total_seconds() / 3600) + 1
        hours = min(hours, 168)  # 最多168小时（7天）
        for i in range(hours):
            hour_start = start_time + timedelta(hours=i)
            hour_end = start_time + timedelta(hours=i + 1)
            hour_stats = queryset.filter(
                timestamp__gte=hour_start,
                timestamp__lt=hour_end,
            ).aggregate(
                total=Sum('total_flow'),
                avg=Avg('total_flow'),
                avg_speed=Avg('avg_speed'),
            )
            flow_data.append({
                'time': hour_start.strftime('%m-%d %H:00'),
                'total': hour_stats['total'] or 0,
                'avg': round(hour_stats['avg'] or 0, 1),
                'avg_speed': round(hour_stats['avg_speed'] or 0, 1),
            })

    # 获取所有监测点位
    locations = TrafficFlow.objects.values_list('location', flat=True).distinct()[:50]

    # 图表数据
    chart_data = json.dumps({
        'labels': [d['time'] for d in flow_data],
        'total_flow': [d['total'] for d in flow_data],
        'avg_speed': [d.get('avg_speed', 0) for d in flow_data],
    })

    context = {
        'flow_data': flow_data,
        'chart_data': chart_data,
        'locations': locations,
        'location': location,
        'time_range': time_range,
        'granularity': granularity,
    }
    return render(request, 'visualization/flow_chart.html', context)


@login_required
def heatmap_view(request):
    """交通热力图视图
    按时间段和监测点位展示流量热力数据
    横轴: 小时（0-23），纵轴: 监测点位
    """
    # 获取日期参数
    date_str = request.GET.get('date', '')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = timezone.now().date()
    else:
        target_date = timezone.now().date()

    # 获取该日期所有监测点位的数据
    day_data = TrafficFlow.objects.filter(timestamp__date=target_date)

    # 获取所有出现的点位
    locations = list(day_data.values_list('location', flat=True).distinct()[:20])

    # 构建热力图数据矩阵：点位 x 小时
    heatmap_data = []
    for loc in locations:
        row = {'location': loc, 'hours': []}
        for hour in range(24):
            flow = day_data.filter(
                location=loc,
                timestamp__hour=hour,
            ).aggregate(total=Sum('total_flow'))['total'] or 0
            row['hours'].append(flow)
        heatmap_data.append(row)

    # 准备前端图表数据
    chart_data = json.dumps({
        'locations': locations,
        'hours': list(range(24)),
        'data': [[h for h in row['hours']] for row in heatmap_data],
    })

    context = {
        'heatmap_data': heatmap_data,
        'chart_data': chart_data,
        'target_date': target_date.strftime('%Y-%m-%d'),
        'locations': locations,
    }
    return render(request, 'visualization/heatmap.html', context)


@login_required
def comparison_view(request):
    """预测对比视图
    对比预测值与实际值，展示模型预测准确性
    """
    # 获取过滤参数
    model_type = request.GET.get('model_type', '')
    location = request.GET.get('location', '')
    time_range = request.GET.get('time_range', '7d')

    now = timezone.now()
    if time_range == '30d':
        start_time = now - timedelta(days=30)
    elif time_range == '24h':
        start_time = now - timedelta(hours=24)
    else:
        start_time = now - timedelta(days=7)

    # 查询有实际值的预测结果
    queryset = PredictionResult.objects.filter(
        actual_flow__isnull=False,
        prediction_time__gte=start_time,
    )
    if model_type:
        queryset = queryset.filter(model_type=model_type)
    if location:
        queryset = queryset.filter(location=location)

    predictions = queryset.order_by('prediction_time')[:200]

    # 计算总体误差统计
    error_stats = queryset.aggregate(
        avg_mae=Avg('mae'),
        avg_rmse=Avg('rmse'),
        avg_mape=Avg('mape'),
        total_count=Count('id'),
    )

    # 准备图表数据
    chart_data = json.dumps({
        'labels': [p.prediction_time.strftime('%m-%d %H:%M') for p in predictions],
        'predicted': [p.predicted_flow for p in predictions],
        'actual': [p.actual_flow for p in predictions],
        'confidence_low': [p.confidence_interval_low for p in predictions if p.confidence_interval_low],
        'confidence_high': [p.confidence_interval_high for p in predictions if p.confidence_interval_high],
    })

    # 获取筛选选项
    model_type_choices = PredictionResult.MODEL_CHOICES
    locations = PredictionResult.objects.values_list('location', flat=True).distinct()[:50]

    context = {
        'predictions': predictions,
        'error_stats': error_stats,
        'chart_data': chart_data,
        'model_type': model_type,
        'location': location,
        'time_range': time_range,
        'model_type_choices': model_type_choices,
        'locations': locations,
    }
    return render(request, 'visualization/comparison.html', context)


@login_required
def analysis_view(request):
    """多维度分析视图
    从时间、空间、天气等多维度分析交通流量模式
    """
    now = timezone.now()
    last_30d = now - timedelta(days=30)

    # 1. 按星期几分析（周一到周日流量模式）
    weekday_data = []
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    for i in range(7):
        # Django的week_day: 1=Sunday, 2=Monday ... 7=Saturday
        django_weekday = (i + 2) if i < 6 else 1
        stats = TrafficFlow.objects.filter(
            timestamp__gte=last_30d,
            timestamp__week_day=django_weekday,
        ).aggregate(
            avg_flow=Avg('total_flow'),
            sum_total_flow=Sum('total_flow'),
            avg_speed=Avg('avg_speed'),
        )
        weekday_data.append({
            'name': weekday_names[i],
            'avg_flow': round(stats['avg_flow'] or 0, 1),
            'total_flow': stats['sum_total_flow'] or 0,
            'avg_speed': round(stats['avg_speed'] or 0, 1),
        })

    # 2. 按小时分析（每小时的平均流量）
    hourly_data = []
    for hour in range(24):
        stats = TrafficFlow.objects.filter(
            timestamp__gte=last_30d,
            timestamp__hour=hour,
        ).aggregate(
            avg_flow=Avg('total_flow'),
            avg_speed=Avg('avg_speed'),
        )
        hourly_data.append({
            'hour': f'{hour:02d}:00',
            'avg_flow': round(stats['avg_flow'] or 0, 1),
            'avg_speed': round(stats['avg_speed'] or 0, 1),
        })

    # 3. 按天气类型分析
    weather_analysis = []
    weather_types = WeatherData.objects.values_list('weather_type', flat=True).distinct()
    for wtype in weather_types:
        # 获取该天气类型出现的日期
        weather_dates = WeatherData.objects.filter(
            weather_type=wtype
        ).values_list('timestamp__date', flat=True).distinct()

        flow_stats = TrafficFlow.objects.filter(
            timestamp__date__in=list(weather_dates)[:30]
        ).aggregate(
            avg_flow=Avg('total_flow'),
            avg_speed=Avg('avg_speed'),
        )

        weather_display = dict(WeatherData.WEATHER_CHOICES).get(wtype, wtype)
        weather_analysis.append({
            'type': weather_display,
            'avg_flow': round(flow_stats['avg_flow'] or 0, 1),
            'avg_speed': round(flow_stats['avg_speed'] or 0, 1),
        })

    # 4. 按数据源分析
    source_analysis = TrafficFlow.objects.filter(
        timestamp__gte=last_30d
    ).values('source').annotate(
        count=Count('id'),
        avg_flow=Avg('total_flow'),
        avg_speed=Avg('avg_speed'),
        avg_confidence=Avg('confidence'),
    ).order_by('-count')

    # 图表数据
    chart_data = json.dumps({
        'weekday': {
            'labels': [d['name'] for d in weekday_data],
            'avg_flow': [d['avg_flow'] for d in weekday_data],
            'avg_speed': [d['avg_speed'] for d in weekday_data],
        },
        'hourly': {
            'labels': [d['hour'] for d in hourly_data],
            'avg_flow': [d['avg_flow'] for d in hourly_data],
            'avg_speed': [d['avg_speed'] for d in hourly_data],
        },
    })

    context = {
        'weekday_data': weekday_data,
        'hourly_data': hourly_data,
        'weather_analysis': weather_analysis,
        'source_analysis': source_analysis,
        'chart_data': chart_data,
    }
    return render(request, 'visualization/analysis.html', context)
