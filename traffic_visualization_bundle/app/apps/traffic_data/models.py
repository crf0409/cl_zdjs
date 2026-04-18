"""交通数据管理模块 - 数据模型（4个核心数据表）"""
from django.db import models
from django.conf import settings


class TrafficFlow(models.Model):
    """表1: 交通流量基础数据表"""
    SOURCE_CHOICES = (
        ('sensor', '传感器'),
        ('camera', '摄像头(YOLO检测)'),
        ('manual', '手动录入'),
        ('api', 'API接入'),
    )
    timestamp = models.DateTimeField('时间戳', db_index=True)
    location = models.CharField('监测点位', max_length=200)
    camera_id = models.CharField('摄像头编号', max_length=50, blank=True)
    vehicle_count = models.IntegerField('车辆数量', default=0)
    pedestrian_count = models.IntegerField('行人数量', default=0)
    bicycle_count = models.IntegerField('自行车数量', default=0)
    motorcycle_count = models.IntegerField('摩托车数量', default=0)
    truck_count = models.IntegerField('卡车数量', default=0)
    total_flow = models.IntegerField('总流量', default=0)
    avg_speed = models.FloatField('平均速度(km/h)', null=True, blank=True)
    occupancy_rate = models.FloatField('道路占有率(%)', null=True, blank=True)
    source = models.CharField('数据源', max_length=20, choices=SOURCE_CHOICES, default='camera')
    confidence = models.FloatField('检测置信度', null=True, blank=True)
    is_cleaned = models.BooleanField('是否已清洗', default=False)
    created_at = models.DateTimeField('录入时间', auto_now_add=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, verbose_name='上传者')

    class Meta:
        verbose_name = '交通流量数据'
        verbose_name_plural = '交通流量数据'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'location']),
            models.Index(fields=['camera_id']),
        ]

    def __str__(self):
        return f"{self.location} - {self.timestamp} - 总流量:{self.total_flow}"

    def save(self, *args, **kwargs):
        self.total_flow = (self.vehicle_count + self.pedestrian_count +
                           self.bicycle_count + self.motorcycle_count + self.truck_count)
        super().save(*args, **kwargs)


class WeatherData(models.Model):
    """表2: 气象关联数据表"""
    WEATHER_CHOICES = (
        ('sunny', '晴天'),
        ('cloudy', '多云'),
        ('rainy', '雨天'),
        ('foggy', '雾天'),
        ('snowy', '雪天'),
        ('overcast', '阴天'),
    )
    timestamp = models.DateTimeField('时间戳', db_index=True)
    location = models.CharField('区域', max_length=200)
    weather_type = models.CharField('天气类型', max_length=20, choices=WEATHER_CHOICES)
    temperature = models.FloatField('温度(°C)')
    humidity = models.FloatField('湿度(%)')
    wind_speed = models.FloatField('风速(m/s)', default=0)
    visibility = models.FloatField('能见度(km)', default=10.0)
    precipitation = models.FloatField('降水量(mm)', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '气象数据'
        verbose_name_plural = '气象数据'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.location} - {self.timestamp} - {self.get_weather_type_display()}"


class TimePeriodLabel(models.Model):
    """表3: 节假日与时段标签表"""
    PERIOD_CHOICES = (
        ('morning_peak', '早高峰(7:00-9:00)'),
        ('evening_peak', '晚高峰(17:00-19:00)'),
        ('daytime', '白天平峰(9:00-17:00)'),
        ('night', '夜间(19:00-7:00)'),
    )
    DAY_TYPE_CHOICES = (
        ('workday', '工作日'),
        ('weekend', '周末'),
        ('holiday', '节假日'),
        ('special', '特殊日期'),
    )
    date = models.DateField('日期', db_index=True)
    period = models.CharField('时段', max_length=20, choices=PERIOD_CHOICES)
    day_type = models.CharField('日期类型', max_length=20, choices=DAY_TYPE_CHOICES, default='workday')
    holiday_name = models.CharField('节假日名称', max_length=50, blank=True)
    is_event = models.BooleanField('是否有大型活动', default=False)
    event_name = models.CharField('活动名称', max_length=100, blank=True)
    flow_factor = models.FloatField('流量系数', default=1.0,
                                     help_text='相对于正常日的流量倍率')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '时段标签'
        verbose_name_plural = '时段标签'
        ordering = ['-date']
        unique_together = ['date', 'period']

    def __str__(self):
        return f"{self.date} - {self.get_period_display()} - {self.get_day_type_display()}"


class PredictionResult(models.Model):
    """表4: 预测结果存储表"""
    MODEL_CHOICES = (
        ('lstm', 'LSTM模型'),
        ('cnn', 'CNN模型'),
        ('lstm_cnn', 'LSTM+CNN混合模型'),
        ('collaborative', '协同过滤'),
    )
    model_type = models.CharField('模型类型', max_length=20, choices=MODEL_CHOICES)
    model_version = models.CharField('模型版本', max_length=50)
    location = models.CharField('预测点位', max_length=200)
    prediction_time = models.DateTimeField('预测目标时间')
    predicted_flow = models.IntegerField('预测流量')
    actual_flow = models.IntegerField('实际流量', null=True, blank=True)
    predicted_vehicle = models.IntegerField('预测车辆数', default=0)
    predicted_pedestrian = models.IntegerField('预测行人数', default=0)
    mae = models.FloatField('MAE', null=True, blank=True)
    rmse = models.FloatField('RMSE', null=True, blank=True)
    mape = models.FloatField('MAPE(%)', null=True, blank=True)
    confidence_interval_low = models.FloatField('置信下界', null=True, blank=True)
    confidence_interval_high = models.FloatField('置信上界', null=True, blank=True)
    created_at = models.DateTimeField('预测生成时间', auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, verbose_name='预测者')

    class Meta:
        verbose_name = '预测结果'
        verbose_name_plural = '预测结果'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['prediction_time', 'location']),
            models.Index(fields=['model_type']),
        ]

    def __str__(self):
        return f"{self.model_type} - {self.location} - {self.prediction_time} - 预测:{self.predicted_flow}"
