#!/usr/bin/env python
"""
初始化数据脚本
生成示例数据并导入到Django数据库中
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'traffic_prediction.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from datetime import datetime, timedelta, date
from django.utils import timezone
from apps.users.models import User, UserActivity
from apps.traffic_data.models import TrafficFlow, WeatherData, TimePeriodLabel, PredictionResult
from apps.prediction.models import TrainedModel, TrainingLog
from apps.reports.models import Report
from utils.data_processor import NuScenesTrafficGenerator
import random
import numpy as np


def create_users():
    """创建示例用户"""
    print("创建用户...")

    # 管理员
    if not User.objects.filter(username='admin').exists():
        admin = User.objects.create_superuser(
            username='admin', email='admin@traffic.com', password='admin123',
            role='admin', department='系统管理部'
        )
        print(f"  管理员: admin / admin123")

    # 数据分析师
    if not User.objects.filter(username='analyst').exists():
        analyst = User.objects.create_user(
            username='analyst', email='analyst@traffic.com', password='analyst123',
            role='analyst', department='数据分析部'
        )
        print(f"  分析师: analyst / analyst123")

    # 普通用户
    if not User.objects.filter(username='user1').exists():
        user = User.objects.create_user(
            username='user1', email='user1@traffic.com', password='user123',
            role='user', department='交通管理部'
        )
        print(f"  普通用户: user1 / user123")


def import_traffic_data():
    """导入交通流量数据"""
    print("生成交通流量数据...")
    generator = NuScenesTrafficGenerator()
    df = generator.generate_traffic_timeseries(days=30)

    print(f"  共 {len(df)} 条记录，开始导入...")
    batch = []
    for _, row in df.iterrows():
        batch.append(TrafficFlow(
            timestamp=timezone.make_aware(row['timestamp']),
            location=row['location'],
            camera_id=row['camera_id'],
            vehicle_count=row['vehicle_count'],
            pedestrian_count=row['pedestrian_count'],
            bicycle_count=row['bicycle_count'],
            motorcycle_count=row['motorcycle_count'],
            truck_count=row['truck_count'],
            total_flow=row['total_flow'],
            avg_speed=row['avg_speed'],
            occupancy_rate=row['occupancy_rate'],
            source=row['source'],
            confidence=row['confidence'],
            is_cleaned=True,
        ))
        if len(batch) >= 1000:
            TrafficFlow.objects.bulk_create(batch)
            batch = []
    if batch:
        TrafficFlow.objects.bulk_create(batch)
    print(f"  导入完成: {TrafficFlow.objects.count()} 条")


def import_weather_data():
    """导入气象数据"""
    print("生成气象数据...")
    generator = NuScenesTrafficGenerator()
    df = generator.generate_weather_data(days=30)

    batch = []
    for _, row in df.iterrows():
        batch.append(WeatherData(
            timestamp=timezone.make_aware(row['timestamp']),
            location=row['location'],
            weather_type=row['weather_type'],
            temperature=row['temperature'],
            humidity=row['humidity'],
            wind_speed=row['wind_speed'],
            visibility=row['visibility'],
            precipitation=row['precipitation'],
        ))
    WeatherData.objects.bulk_create(batch)
    print(f"  导入完成: {WeatherData.objects.count()} 条")


def import_time_labels():
    """导入时段标签"""
    print("生成时段标签...")
    generator = NuScenesTrafficGenerator()
    df = generator.generate_time_labels(days=30)

    batch = []
    for _, row in df.iterrows():
        batch.append(TimePeriodLabel(
            date=row['date'],
            period=row['period'],
            day_type=row['day_type'],
            holiday_name=row['holiday_name'],
            is_event=row['is_event'],
            event_name=row['event_name'],
            flow_factor=row['flow_factor'],
        ))
    TimePeriodLabel.objects.bulk_create(batch)
    print(f"  导入完成: {TimePeriodLabel.objects.count()} 条")


def create_sample_models():
    """创建示例训练模型记录"""
    print("创建模型记录...")
    user = User.objects.filter(role='analyst').first() or User.objects.first()

    models_data = [
        {
            'name': 'LSTM交通流量预测v1',
            'model_type': 'lstm',
            'version': '1.0.0',
            'status': 'deployed',
            'epochs': 50,
            'batch_size': 32,
            'learning_rate': 0.001,
            'sequence_length': 24,
            'train_loss': 0.0234,
            'val_loss': 0.0312,
            'mae': 2.15,
            'rmse': 3.42,
            'mape': 8.7,
            'r2_score': 0.923,
            'training_time': 145.6,
            'description': '基于LSTM的交通流量时序预测模型，使用nuScenes数据集训练',
        },
        {
            'name': 'CNN特征提取v1',
            'model_type': 'cnn',
            'version': '1.0.0',
            'status': 'completed',
            'epochs': 30,
            'batch_size': 64,
            'learning_rate': 0.0005,
            'sequence_length': 12,
            'train_loss': 0.0189,
            'val_loss': 0.0278,
            'mae': 1.98,
            'rmse': 3.15,
            'mape': 7.9,
            'r2_score': 0.935,
            'training_time': 89.3,
            'description': 'CNN模型用于交通数据空间特征提取',
        },
        {
            'name': 'LSTM+CNN混合模型v1',
            'model_type': 'lstm_cnn',
            'version': '1.0.0',
            'status': 'deployed',
            'epochs': 80,
            'batch_size': 32,
            'learning_rate': 0.0008,
            'sequence_length': 24,
            'train_loss': 0.0156,
            'val_loss': 0.0223,
            'mae': 1.67,
            'rmse': 2.78,
            'mape': 6.5,
            'r2_score': 0.951,
            'training_time': 267.8,
            'description': 'LSTM+CNN混合架构，结合时序特征与空间特征，性能最优',
        },
        {
            'name': '协同过滤推荐v1',
            'model_type': 'collaborative',
            'version': '1.0.0',
            'status': 'completed',
            'epochs': 20,
            'batch_size': 128,
            'learning_rate': 0.01,
            'sequence_length': 48,
            'train_loss': 0.0345,
            'val_loss': 0.0401,
            'mae': 2.89,
            'rmse': 4.12,
            'mape': 11.3,
            'r2_score': 0.887,
            'training_time': 34.5,
            'description': '基于协同过滤的交通模式推荐，利用相似路段历史模式预测',
        },
    ]

    for md in models_data:
        model = TrainedModel.objects.create(created_by=user, **md)

        # 创建训练日志
        for epoch in range(1, md['epochs'] + 1):
            progress = epoch / md['epochs']
            TrainingLog.objects.create(
                model=model,
                epoch=epoch,
                train_loss=md['train_loss'] / progress * 2 * (1 + random.gauss(0, 0.05)),
                val_loss=(md['val_loss'] / progress * 2 * (1 + random.gauss(0, 0.08))
                          if md['val_loss'] else None),
                learning_rate=md['learning_rate'] * (0.95 ** (epoch // 10)),
            )

    print(f"  创建完成: {TrainedModel.objects.count()} 个模型")


def create_prediction_results():
    """创建示例预测结果"""
    print("创建预测结果...")
    user = User.objects.filter(role='analyst').first() or User.objects.first()
    locations = ['CAM_FRONT_主干道A', 'CAM_FRONT_商业区B', 'CAM_FRONT_住宅区C']
    model_types = ['lstm', 'cnn', 'lstm_cnn']

    batch = []
    start = datetime(2024, 1, 25, 0, 0, 0)

    for day in range(5):
        for hour in range(24):
            ts = start + timedelta(days=day, hours=hour)
            for loc in locations:
                for mt in model_types:
                    # 模拟真实流量
                    base = 8 if 0 <= hour < 6 else (25 if 7 <= hour <= 9 or 17 <= hour <= 19 else 15)
                    actual = max(0, int(base + random.gauss(0, 3)))

                    # 模拟预测（不同模型精度不同）
                    noise = {'lstm': 2.5, 'cnn': 2.2, 'lstm_cnn': 1.8}
                    predicted = max(0, int(actual + random.gauss(0, noise[mt])))

                    error = abs(actual - predicted)
                    batch.append(PredictionResult(
                        model_type=mt,
                        model_version='1.0.0',
                        location=loc,
                        prediction_time=timezone.make_aware(ts),
                        predicted_flow=predicted,
                        actual_flow=actual,
                        predicted_vehicle=max(0, int(predicted * 0.75)),
                        predicted_pedestrian=max(0, int(predicted * 0.15)),
                        mae=round(error, 2),
                        rmse=round(error * 1.2, 2),
                        mape=round(error / max(actual, 1) * 100, 2),
                        confidence_interval_low=max(0, predicted - 4),
                        confidence_interval_high=predicted + 4,
                        created_by=user,
                    ))

    PredictionResult.objects.bulk_create(batch)
    print(f"  创建完成: {PredictionResult.objects.count()} 条预测")


def create_activity_logs():
    """创建示例活动日志"""
    print("创建活动日志...")
    users = list(User.objects.all())
    actions = ['login', 'view', 'upload', 'train', 'predict', 'export']

    batch = []
    for i in range(100):
        user = random.choice(users)
        action = random.choice(actions)
        ts = timezone.now() - timedelta(hours=random.randint(1, 720))
        batch.append(UserActivity(
            user=user,
            action=action,
            detail=f'{user.username} 执行了 {action} 操作',
            ip_address=f'192.168.1.{random.randint(1, 254)}',
        ))
    UserActivity.objects.bulk_create(batch)
    print(f"  创建完成: {UserActivity.objects.count()} 条日志")


def main():
    print("=" * 50)
    print("智能交通流量预测系统 - 数据初始化")
    print("=" * 50)

    # 清空旧数据
    print("\n清空旧数据...")
    TrafficFlow.objects.all().delete()
    WeatherData.objects.all().delete()
    TimePeriodLabel.objects.all().delete()
    PredictionResult.objects.all().delete()
    TrainedModel.objects.all().delete()
    TrainingLog.objects.all().delete()
    UserActivity.objects.all().delete()
    Report.objects.all().delete()

    create_users()
    import_traffic_data()
    import_weather_data()
    import_time_labels()
    create_sample_models()
    create_prediction_results()
    create_activity_logs()

    print("\n" + "=" * 50)
    print("数据初始化完成!")
    print(f"  用户: {User.objects.count()}")
    print(f"  交通数据: {TrafficFlow.objects.count()}")
    print(f"  气象数据: {WeatherData.objects.count()}")
    print(f"  时段标签: {TimePeriodLabel.objects.count()}")
    print(f"  预测模型: {TrainedModel.objects.count()}")
    print(f"  预测结果: {PredictionResult.objects.count()}")
    print(f"  活动日志: {UserActivity.objects.count()}")
    print("=" * 50)


if __name__ == '__main__':
    main()
