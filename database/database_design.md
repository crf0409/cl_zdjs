# 智能交通流量预测系统 - 数据库设计文档

## 1. 数据库概述

| 项目 | 说明 |
|------|------|
| 数据库名 | `smart_traffic` |
| 数据库引擎 | MySQL 8.0+ / SQLite 3 (开发环境) |
| 字符集 | utf8mb4 |
| 排序规则 | utf8mb4_unicode_ci |
| 业务表数量 | 9 张 |

## 2. ER 关系图 (文本表示)

```
┌─────────────────┐       ┌──────────────────────┐
│   users_user    │       │ users_useractivity   │
│─────────────────│       │──────────────────────│
│ PK id           │◄──┐   │ PK id                │
│    username     │   └───│ FK user_id           │
│    role         │       │    action             │
│    department   │       │    detail             │
│    phone        │       │    ip_address         │
│    ...          │       │    created_at         │
└────────┬────────┘       └──────────────────────┘
         │
         │ (uploaded_by / created_by)
         │
    ┌────┴────────────────────────────────────────┐
    │                    │                         │
    ▼                    ▼                         ▼
┌──────────────────┐  ┌───────────────────┐  ┌───────────────┐
│traffic_data_     │  │traffic_data_      │  │reports_report │
│ trafficflow      │  │ predictionresult  │  │───────────────│
│──────────────────│  │───────────────────│  │ PK id         │
│ PK id            │  │ PK id             │  │    title      │
│    timestamp     │  │    model_type     │  │    report_type│
│    location      │  │    location       │  │    format     │
│    camera_id     │  │    prediction_time│  │    file_path  │
│    vehicle_count │  │    predicted_flow │  │ FK created_by │
│    total_flow    │  │    actual_flow    │  │    created_at │
│    avg_speed     │  │    mae/rmse/mape  │  └───────────────┘
│    source        │  │ FK created_by_id  │
│ FK uploaded_by_id│  │    created_at     │
│    created_at    │  └───────────────────┘
└──────────────────┘
                         ┌───────────────────────┐
┌──────────────────┐     │prediction_trainedmodel│
│traffic_data_     │     │───────────────────────│
│ weatherdata      │     │ PK id                 │
│──────────────────│     │    name               │◄────┐
│ PK id            │     │    model_type         │     │
│    timestamp     │     │    version / status   │     │
│    location      │     │    epochs/batch_size  │     │
│    weather_type  │     │    mae/rmse/r2_score  │     │
│    temperature   │     │ FK created_by_id      │     │
│    humidity      │     │    created_at         │     │
└──────────────────┘     └───────────────────────┘     │
                                                        │
┌──────────────────┐     ┌───────────────────────┐     │
│traffic_data_     │     │prediction_traininglog │     │
│timeperiodlabel   │     │───────────────────────│     │
│──────────────────│     │ PK id                 │     │
│ PK id            │     │ FK model_id ──────────┼─────┘
│    date          │     │    epoch              │
│    period        │     │    train_loss         │
│    day_type      │     │    val_loss           │
│    holiday_name  │     │    learning_rate      │
│    flow_factor   │     │    timestamp          │
└──────────────────┘     └───────────────────────┘
```

## 3. 表详细设计

### 3.1 用户表 `users_user`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK, AUTO_INCREMENT | 用户ID |
| username | VARCHAR(150) | UNIQUE, NOT NULL | 用户名 |
| password | VARCHAR(128) | NOT NULL | 密码(PBKDF2哈希) |
| email | VARCHAR(254) | | 邮箱 |
| role | VARCHAR(20) | DEFAULT 'user' | 角色: admin/analyst/user |
| phone | VARCHAR(15) | | 手机号 |
| department | VARCHAR(100) | | 所属部门 |
| avatar | VARCHAR(100) | | 头像文件路径 |
| is_superuser | TINYINT(1) | DEFAULT 0 | 超级管理员标识 |
| is_staff | TINYINT(1) | DEFAULT 0 | 后台访问权限 |
| is_active | TINYINT(1) | DEFAULT 1 | 账户激活状态 |
| last_login | DATETIME(6) | NULL | 最后登录时间 |
| date_joined | DATETIME(6) | NOT NULL | 注册时间 |
| created_at | DATETIME(6) | NOT NULL | 创建时间 |
| updated_at | DATETIME(6) | NOT NULL | 更新时间 |

**角色权限说明：**
- `admin` - 管理员：全部权限，可管理用户和系统配置
- `analyst` - 数据分析师：可训练模型、执行预测、生成报告
- `user` - 普通用户：可查看数据和预测结果

### 3.2 用户活动表 `users_useractivity`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK | 记录ID |
| user_id | BIGINT | FK → users_user | 操作用户 |
| action | VARCHAR(20) | NOT NULL | 操作类型 |
| detail | TEXT | | 操作详情 |
| ip_address | VARCHAR(39) | NULL | 客户端IP |
| created_at | DATETIME(6) | NOT NULL | 操作时间 |

**操作类型枚举：** login / logout / upload / train / predict / export / view

### 3.3 交通流量表 `traffic_data_trafficflow`（核心表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK | 记录ID |
| timestamp | DATETIME(6) | NOT NULL, INDEX | 采集时间 |
| location | VARCHAR(200) | NOT NULL | 监测点位 |
| camera_id | VARCHAR(50) | INDEX | 摄像头编号 |
| vehicle_count | INT | DEFAULT 0 | 车辆数 |
| pedestrian_count | INT | DEFAULT 0 | 行人数 |
| bicycle_count | INT | DEFAULT 0 | 自行车数 |
| motorcycle_count | INT | DEFAULT 0 | 摩托车数 |
| truck_count | INT | DEFAULT 0 | 卡车数 |
| total_flow | INT | DEFAULT 0 | 总流量（自动计算） |
| avg_speed | DOUBLE | NULL | 平均车速(km/h) |
| occupancy_rate | DOUBLE | NULL | 道路占有率(%) |
| source | VARCHAR(20) | DEFAULT 'camera' | 数据来源 |
| confidence | DOUBLE | NULL | YOLO检测置信度 |
| is_cleaned | TINYINT(1) | DEFAULT 0 | 是否已清洗 |
| uploaded_by_id | BIGINT | FK → users_user, NULL | 上传者 |
| created_at | DATETIME(6) | NOT NULL | 入库时间 |

**复合索引：** `(timestamp, location)` — 加速按时间+地点的联合查询

**数据来源枚举：**
- `sensor` - 路面传感器
- `camera` - 摄像头(YOLO目标检测)
- `manual` - 人工录入
- `api` - 第三方API接入

### 3.4 气象数据表 `traffic_data_weatherdata`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK | 记录ID |
| timestamp | DATETIME(6) | NOT NULL, INDEX | 时间 |
| location | VARCHAR(200) | NOT NULL | 区域 |
| weather_type | VARCHAR(20) | NOT NULL | 天气类型 |
| temperature | DOUBLE | NOT NULL | 温度(°C) |
| humidity | DOUBLE | NOT NULL | 湿度(%) |
| wind_speed | DOUBLE | DEFAULT 0 | 风速(m/s) |
| visibility | DOUBLE | DEFAULT 10.0 | 能见度(km) |
| precipitation | DOUBLE | DEFAULT 0 | 降水量(mm) |

**天气类型：** sunny / cloudy / rainy / foggy / snowy / overcast

### 3.5 时段标签表 `traffic_data_timeperiodlabel`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK | 记录ID |
| date | DATE | NOT NULL | 日期 |
| period | VARCHAR(20) | NOT NULL | 时段 |
| day_type | VARCHAR(20) | DEFAULT 'workday' | 日期类型 |
| holiday_name | VARCHAR(50) | | 节假日名称 |
| is_event | TINYINT(1) | DEFAULT 0 | 是否有活动 |
| event_name | VARCHAR(100) | | 活动名称 |
| flow_factor | DOUBLE | DEFAULT 1.0 | 流量系数 |

**唯一约束：** `(date, period)` — 同一天同一时段不可重复

### 3.6 预测结果表 `traffic_data_predictionresult`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK | 记录ID |
| model_type | VARCHAR(20) | NOT NULL, INDEX | 模型类型 |
| model_version | VARCHAR(50) | NOT NULL | 模型版本 |
| location | VARCHAR(200) | NOT NULL | 预测点位 |
| prediction_time | DATETIME(6) | NOT NULL | 预测目标时间 |
| predicted_flow | INT | NOT NULL | 预测流量 |
| actual_flow | INT | NULL | 实际流量 |
| predicted_vehicle | INT | DEFAULT 0 | 预测车辆数 |
| predicted_pedestrian | INT | DEFAULT 0 | 预测行人数 |
| mae | DOUBLE | NULL | MAE指标 |
| rmse | DOUBLE | NULL | RMSE指标 |
| mape | DOUBLE | NULL | MAPE(%)指标 |
| confidence_interval_low | DOUBLE | NULL | 置信下界 |
| confidence_interval_high | DOUBLE | NULL | 置信上界 |
| created_by_id | BIGINT | FK, NULL | 预测者 |

### 3.7 训练模型表 `prediction_trainedmodel`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK | 模型ID |
| name | VARCHAR(100) | NOT NULL | 模型名称 |
| model_type | VARCHAR(20) | NOT NULL | 类型 |
| version | VARCHAR(50) | NOT NULL | 版本号 |
| status | VARCHAR(20) | DEFAULT 'training' | 状态 |
| epochs | INT | DEFAULT 50 | 训练轮次 |
| batch_size | INT | DEFAULT 32 | 批次大小 |
| learning_rate | DOUBLE | DEFAULT 0.001 | 学习率 |
| sequence_length | INT | DEFAULT 24 | 序列长度 |
| train_loss | DOUBLE | NULL | 训练损失 |
| val_loss | DOUBLE | NULL | 验证损失 |
| mae / rmse / mape / r2_score | DOUBLE | NULL | 性能指标 |
| training_time | DOUBLE | NULL | 耗时(秒) |
| description | TEXT | | 描述 |
| file_path | VARCHAR(100) | | 模型文件路径 |

### 3.8 训练日志表 `prediction_traininglog`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK | 日志ID |
| model_id | BIGINT | FK → trainedmodel | 所属模型 |
| epoch | INT | NOT NULL | 轮次 |
| train_loss | DOUBLE | NOT NULL | 训练损失 |
| val_loss | DOUBLE | NULL | 验证损失 |
| learning_rate | DOUBLE | NOT NULL | 学习率 |
| timestamp | DATETIME(6) | NOT NULL | 记录时间 |

### 3.9 报告表 `reports_report`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK | 报告ID |
| title | VARCHAR(200) | NOT NULL | 标题 |
| report_type | VARCHAR(20) | NOT NULL | 类型 |
| format | VARCHAR(10) | NOT NULL | 格式: pdf/excel/word |
| file_path | VARCHAR(100) | NOT NULL | 文件路径 |
| description | TEXT | | 描述 |
| date_from / date_to | DATE | NULL | 数据时间范围 |
| file_size | INT | DEFAULT 0 | 文件大小 |
| created_by_id | BIGINT | FK, NULL | 创建者 |

## 4. 表间关系汇总

| 外键 | 主表 | 从表 | 关系 | 删除策略 |
|------|------|------|------|----------|
| user_id | users_user | users_useractivity | 1:N | CASCADE |
| uploaded_by_id | users_user | traffic_data_trafficflow | 1:N | SET NULL |
| created_by_id | users_user | traffic_data_predictionresult | 1:N | SET NULL |
| created_by_id | users_user | prediction_trainedmodel | 1:N | SET NULL |
| model_id | prediction_trainedmodel | prediction_traininglog | 1:N | CASCADE |
| created_by_id | users_user | reports_report | 1:N | SET NULL |

## 5. 索引策略

| 表 | 索引名 | 字段 | 用途 |
|----|--------|------|------|
| trafficflow | idx_flow_ts_loc | (timestamp, location) | 时间+地点联合查询 |
| trafficflow | idx_flow_camera | (camera_id) | 按摄像头查询 |
| predictionresult | idx_pred_time_loc | (prediction_time, location) | 预测结果查询 |
| predictionresult | idx_pred_model | (model_type) | 按模型类型筛选 |
| trainedmodel | idx_model_status | (status) | 按状态筛选模型 |
| weatherdata | idx_weather_timestamp | (timestamp) | 时间查询 |
| timeperiodlabel | uq_date_period | (date, period) | 唯一约束+查询 |

## 6. 数据量预估

| 表 | 初始数据量 | 月增量 | 说明 |
|----|-----------|--------|------|
| trafficflow | ~21,600 | ~43,200 | 6个点位×24h×30天×每小时5条 |
| weatherdata | ~4,320 | ~8,640 | 6个点位×24h×30天 |
| timeperiodlabel | ~120 | ~120 | 30天×4时段 |
| predictionresult | ~10,800 | ~21,600 | 3种模型×3点位×24h×5天 |
| trainedmodel | 4 | ~2 | 按需训练 |
| traininglog | ~720 | ~200 | 每模型50-80轮 |
