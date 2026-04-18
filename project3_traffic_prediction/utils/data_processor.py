"""
数据处理工具模块
从nuScenes自动驾驶数据集生成交通流量数据
"""
import os
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


class NuScenesTrafficGenerator:
    """从nuScenes YOLO检测结果生成交通流量时序数据"""

    # nuScenes中的交通相关类别
    VEHICLE_CLASSES = {'car', 'truck', 'bus'}
    PEDESTRIAN_CLASSES = {'person'}
    BICYCLE_CLASSES = {'bicycle'}
    MOTORCYCLE_CLASSES = {'motorcycle'}

    def __init__(self, yolo_results_dir=None):
        self.yolo_results_dir = yolo_results_dir
        self.base_stats = {
            'vehicle': 10.3,  # avg vehicles per frame from experiments
            'pedestrian': 2.0,
            'bicycle': 0.12,
            'motorcycle': 0.38,
            'truck': 0.37,
        }

    def generate_traffic_timeseries(self, days=30, interval_minutes=15,
                                     locations=None):
        """
        基于nuScenes检测统计生成扩展的交通流量时序数据

        Args:
            days: 生成天数
            interval_minutes: 数据间隔（分钟）
            locations: 监测点列表

        Returns:
            DataFrame with traffic flow data
        """
        if locations is None:
            locations = [
                'Main_Road_A',
                'Commercial_District_B',
                'Residential_Area_C',
                'Side_Road_D',
                'Intersection_E',
                'Highway_Entrance_F',
            ]

        records = []
        start_date = datetime(2024, 1, 1, 0, 0, 0)
        points_per_day = 24 * 60 // interval_minutes

        for day in range(days):
            current_date = start_date + timedelta(days=day)
            weekday = current_date.weekday()
            is_weekend = weekday >= 5

            # 节假日模拟
            is_holiday = day in [0, 1, 2, 24, 25, 26]  # 元旦假期 + 模拟春节

            for loc_idx, location in enumerate(locations):
                # 位置系数 - 不同位置的基础流量不同
                loc_factor = [1.0, 1.3, 0.7, 0.5, 0.9, 1.5][loc_idx]

                for t in range(points_per_day):
                    hour = (t * interval_minutes) // 60
                    minute = (t * interval_minutes) % 60
                    ts = current_date.replace(hour=hour, minute=minute)

                    # 时间模式系数
                    time_factor = self._get_time_factor(hour, is_weekend, is_holiday)

                    # 天气影响（随机）
                    weather_factor = random.uniform(0.85, 1.15)

                    # 生成各类交通参与者数量
                    base_factor = time_factor * loc_factor * weather_factor
                    noise = lambda: max(0, random.gauss(0, 0.15))

                    vehicle = max(0, int(self.base_stats['vehicle'] * base_factor * (1 + noise()) + 0.5))
                    pedestrian = max(0, int(self.base_stats['pedestrian'] * base_factor * 1.2 * (1 + noise()) + 0.5))
                    bicycle = max(0, int(self.base_stats['bicycle'] * base_factor * (1 + noise()) + 0.5))
                    motorcycle = max(0, int(self.base_stats['motorcycle'] * base_factor * (1 + noise()) + 0.5))
                    truck = max(0, int(self.base_stats['truck'] * base_factor * 0.8 * (1 + noise()) + 0.5))

                    total = vehicle + pedestrian + bicycle + motorcycle + truck

                    # 估算平均速度（与流量负相关）
                    avg_speed = max(5, 60 - total * 1.2 + random.gauss(0, 3))

                    # 道路占有率
                    occupancy = min(95, max(2, total * 2.5 + random.gauss(0, 3)))

                    # 置信度
                    confidence = round(random.uniform(0.55, 0.92), 3)

                    records.append({
                        'timestamp': ts,
                        'location': location,
                        'camera_id': f'CAM_{loc_idx:03d}',
                        'vehicle_count': vehicle,
                        'pedestrian_count': pedestrian,
                        'bicycle_count': bicycle,
                        'motorcycle_count': motorcycle,
                        'truck_count': truck,
                        'total_flow': total,
                        'avg_speed': round(avg_speed, 1),
                        'occupancy_rate': round(occupancy, 1),
                        'source': 'camera',
                        'confidence': confidence,
                    })

        df = pd.DataFrame(records)
        return df

    def _get_time_factor(self, hour, is_weekend, is_holiday):
        """获取时段流量系数"""
        if is_holiday:
            # 节假日模式
            factors = {
                range(0, 6): 0.15,
                range(6, 8): 0.3,
                range(8, 10): 0.6,
                range(10, 14): 0.9,
                range(14, 17): 0.85,
                range(17, 20): 0.7,
                range(20, 22): 0.4,
                range(22, 24): 0.2,
            }
        elif is_weekend:
            # 周末模式
            factors = {
                range(0, 6): 0.1,
                range(6, 8): 0.25,
                range(8, 10): 0.5,
                range(10, 14): 0.8,
                range(14, 17): 0.75,
                range(17, 20): 0.65,
                range(20, 22): 0.35,
                range(22, 24): 0.15,
            }
        else:
            # 工作日模式 - 双峰
            factors = {
                range(0, 5): 0.08,
                range(5, 6): 0.2,
                range(6, 7): 0.5,
                range(7, 8): 1.0,    # 早高峰
                range(8, 9): 1.2,    # 早高峰峰值
                range(9, 10): 0.8,
                range(10, 12): 0.6,
                range(12, 14): 0.7,  # 午间略升
                range(14, 17): 0.6,
                range(17, 18): 1.0,  # 晚高峰
                range(18, 19): 1.15, # 晚高峰峰值
                range(19, 20): 0.7,
                range(20, 22): 0.35,
                range(22, 24): 0.15,
            }

        for time_range, factor in factors.items():
            if hour in time_range:
                return factor
        return 0.3

    def generate_weather_data(self, days=30, locations=None):
        """生成气象数据"""
        if locations is None:
            locations = ['城区']

        records = []
        start_date = datetime(2024, 1, 1)

        weather_types = ['sunny', 'cloudy', 'rainy', 'foggy', 'overcast']
        weather_probs = [0.35, 0.25, 0.15, 0.05, 0.20]

        for day in range(days):
            date = start_date + timedelta(days=day)
            weather = random.choices(weather_types, weather_probs)[0]

            base_temp = 5 + 10 * np.sin(2 * np.pi * (day - 30) / 365)  # 季节变化

            for hour in range(0, 24, 3):  # 每3小时一条
                ts = date.replace(hour=hour)
                temp_variation = -3 + 6 * np.sin(2 * np.pi * (hour - 6) / 24)  # 日变化

                for loc in locations:
                    records.append({
                        'timestamp': ts,
                        'location': loc,
                        'weather_type': weather,
                        'temperature': round(base_temp + temp_variation + random.gauss(0, 1), 1),
                        'humidity': round(min(100, max(20, 60 + random.gauss(0, 15))), 1),
                        'wind_speed': round(max(0, random.gauss(3, 2)), 1),
                        'visibility': round(max(0.1, 10 - (5 if weather == 'foggy' else 0) + random.gauss(0, 1)), 1),
                        'precipitation': round(max(0, random.gauss(2, 3) if weather == 'rainy' else 0), 1),
                    })

        return pd.DataFrame(records)

    def generate_time_labels(self, days=30):
        """生成时段标签数据"""
        records = []
        start_date = datetime(2024, 1, 1).date()

        holidays = {0: '元旦', 1: '元旦', 2: '元旦', 24: '春节', 25: '春节', 26: '春节'}
        periods = ['morning_peak', 'daytime', 'evening_peak', 'night']

        for day in range(days):
            date = start_date + timedelta(days=day)
            weekday = date.weekday()

            if day in holidays:
                day_type = 'holiday'
                holiday_name = holidays[day]
            elif weekday >= 5:
                day_type = 'weekend'
                holiday_name = ''
            else:
                day_type = 'workday'
                holiday_name = ''

            flow_factors = {
                'workday': {'morning_peak': 1.3, 'daytime': 0.8, 'evening_peak': 1.25, 'night': 0.3},
                'weekend': {'morning_peak': 0.6, 'daytime': 0.9, 'evening_peak': 0.7, 'night': 0.35},
                'holiday': {'morning_peak': 0.5, 'daytime': 1.0, 'evening_peak': 0.8, 'night': 0.4},
            }

            for period in periods:
                records.append({
                    'date': date,
                    'period': period,
                    'day_type': day_type,
                    'holiday_name': holiday_name,
                    'is_event': False,
                    'event_name': '',
                    'flow_factor': flow_factors[day_type][period],
                })

        return pd.DataFrame(records)


def generate_all_sample_data(output_dir, days=30):
    """生成所有示例数据并保存为CSV"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = NuScenesTrafficGenerator()

    print("生成交通流量数据...")
    traffic_df = generator.generate_traffic_timeseries(days=days)
    traffic_df.to_csv(output_dir / 'traffic_flow.csv', index=False)
    print(f"  -> {len(traffic_df)} 条记录")

    print("生成气象数据...")
    weather_df = generator.generate_weather_data(days=days)
    weather_df.to_csv(output_dir / 'weather_data.csv', index=False)
    print(f"  -> {len(weather_df)} 条记录")

    print("生成时段标签...")
    labels_df = generator.generate_time_labels(days=days)
    labels_df.to_csv(output_dir / 'time_labels.csv', index=False)
    print(f"  -> {len(labels_df)} 条记录")

    print(f"\n数据已保存至: {output_dir}")
    return traffic_df, weather_df, labels_df


if __name__ == '__main__':
    data_dir = Path(__file__).parent.parent / 'data'
    generate_all_sample_data(data_dir)
