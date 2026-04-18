-- ============================================================
-- 智能交通流量预测系统 - 数据库初始化脚本
-- 功能：创建数据库、所有业务表及索引
-- 数据库：MySQL 8.0+
-- 字符集：utf8mb4
-- ============================================================

-- 1. 创建数据库
CREATE DATABASE IF NOT EXISTS smart_traffic
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE smart_traffic;

-- ============================================================
-- 2. 用户管理模块
-- ============================================================

-- 2.1 用户表（自定义Django用户模型）
CREATE TABLE IF NOT EXISTS `users_user` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    `password` VARCHAR(128) NOT NULL COMMENT '密码哈希',
    `last_login` DATETIME(6) NULL COMMENT '最后登录时间',
    `is_superuser` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否超级管理员',
    `username` VARCHAR(150) NOT NULL UNIQUE COMMENT '用户名',
    `first_name` VARCHAR(150) NOT NULL DEFAULT '' COMMENT '名',
    `last_name` VARCHAR(150) NOT NULL DEFAULT '' COMMENT '姓',
    `email` VARCHAR(254) NOT NULL DEFAULT '' COMMENT '邮箱',
    `is_staff` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否可以访问管理后台',
    `is_active` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否激活',
    `date_joined` DATETIME(6) NOT NULL COMMENT '注册时间',
    -- 自定义字段
    `role` VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT '角色: admin/analyst/user',
    `phone` VARCHAR(15) NOT NULL DEFAULT '' COMMENT '手机号',
    `avatar` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '头像路径',
    `department` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '部门',
    `created_at` DATETIME(6) NOT NULL COMMENT '创建时间',
    `updated_at` DATETIME(6) NOT NULL COMMENT '更新时间',
    INDEX `idx_users_role` (`role`),
    INDEX `idx_users_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 2.2 用户活动记录表
CREATE TABLE IF NOT EXISTS `users_useractivity` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
    `user_id` BIGINT NOT NULL COMMENT '用户ID',
    `action` VARCHAR(20) NOT NULL COMMENT '操作类型: login/logout/upload/train/predict/export/view',
    `detail` LONGTEXT NOT NULL COMMENT '操作详情',
    `ip_address` VARCHAR(39) NULL COMMENT 'IP地址',
    `created_at` DATETIME(6) NOT NULL COMMENT '操作时间',
    CONSTRAINT `fk_activity_user` FOREIGN KEY (`user_id`) REFERENCES `users_user` (`id`) ON DELETE CASCADE,
    INDEX `idx_activity_user` (`user_id`),
    INDEX `idx_activity_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户活动记录表';

-- ============================================================
-- 3. 交通数据管理模块
-- ============================================================

-- 3.1 交通流量基础数据表
CREATE TABLE IF NOT EXISTS `traffic_data_trafficflow` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
    `timestamp` DATETIME(6) NOT NULL COMMENT '采集时间戳',
    `location` VARCHAR(200) NOT NULL COMMENT '监测点位名称',
    `camera_id` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '摄像头编号',
    `vehicle_count` INT NOT NULL DEFAULT 0 COMMENT '车辆数量',
    `pedestrian_count` INT NOT NULL DEFAULT 0 COMMENT '行人数量',
    `bicycle_count` INT NOT NULL DEFAULT 0 COMMENT '自行车数量',
    `motorcycle_count` INT NOT NULL DEFAULT 0 COMMENT '摩托车数量',
    `truck_count` INT NOT NULL DEFAULT 0 COMMENT '卡车数量',
    `total_flow` INT NOT NULL DEFAULT 0 COMMENT '总流量(各类目之和)',
    `avg_speed` DOUBLE NULL COMMENT '平均速度(km/h)',
    `occupancy_rate` DOUBLE NULL COMMENT '道路占有率(%)',
    `source` VARCHAR(20) NOT NULL DEFAULT 'camera' COMMENT '数据源: sensor/camera/manual/api',
    `confidence` DOUBLE NULL COMMENT 'YOLO检测置信度',
    `is_cleaned` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已清洗',
    `created_at` DATETIME(6) NOT NULL COMMENT '录入时间',
    `uploaded_by_id` BIGINT NULL COMMENT '上传者ID',
    CONSTRAINT `fk_flow_user` FOREIGN KEY (`uploaded_by_id`) REFERENCES `users_user` (`id`) ON DELETE SET NULL,
    INDEX `idx_flow_timestamp` (`timestamp`),
    INDEX `idx_flow_ts_loc` (`timestamp`, `location`),
    INDEX `idx_flow_camera` (`camera_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='交通流量基础数据表';

-- 3.2 气象关联数据表
CREATE TABLE IF NOT EXISTS `traffic_data_weatherdata` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
    `timestamp` DATETIME(6) NOT NULL COMMENT '时间戳',
    `location` VARCHAR(200) NOT NULL COMMENT '区域',
    `weather_type` VARCHAR(20) NOT NULL COMMENT '天气类型: sunny/cloudy/rainy/foggy/snowy/overcast',
    `temperature` DOUBLE NOT NULL COMMENT '温度(摄氏度)',
    `humidity` DOUBLE NOT NULL COMMENT '湿度(%)',
    `wind_speed` DOUBLE NOT NULL DEFAULT 0 COMMENT '风速(m/s)',
    `visibility` DOUBLE NOT NULL DEFAULT 10.0 COMMENT '能见度(km)',
    `precipitation` DOUBLE NOT NULL DEFAULT 0 COMMENT '降水量(mm)',
    `created_at` DATETIME(6) NOT NULL COMMENT '创建时间',
    INDEX `idx_weather_timestamp` (`timestamp`),
    INDEX `idx_weather_location` (`location`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='气象关联数据表';

-- 3.3 节假日与时段标签表
CREATE TABLE IF NOT EXISTS `traffic_data_timeperiodlabel` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
    `date` DATE NOT NULL COMMENT '日期',
    `period` VARCHAR(20) NOT NULL COMMENT '时段: morning_peak/evening_peak/daytime/night',
    `day_type` VARCHAR(20) NOT NULL DEFAULT 'workday' COMMENT '日期类型: workday/weekend/holiday/special',
    `holiday_name` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '节假日名称',
    `is_event` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否有大型活动',
    `event_name` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '活动名称',
    `flow_factor` DOUBLE NOT NULL DEFAULT 1.0 COMMENT '流量系数(相对正常日的倍率)',
    `created_at` DATETIME(6) NOT NULL COMMENT '创建时间',
    UNIQUE KEY `uq_date_period` (`date`, `period`),
    INDEX `idx_label_date` (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='节假日与时段标签表';

-- 3.4 预测结果存储表
CREATE TABLE IF NOT EXISTS `traffic_data_predictionresult` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
    `model_type` VARCHAR(20) NOT NULL COMMENT '模型类型: lstm/cnn/lstm_cnn/collaborative',
    `model_version` VARCHAR(50) NOT NULL COMMENT '模型版本号',
    `location` VARCHAR(200) NOT NULL COMMENT '预测点位',
    `prediction_time` DATETIME(6) NOT NULL COMMENT '预测目标时间',
    `predicted_flow` INT NOT NULL COMMENT '预测总流量',
    `actual_flow` INT NULL COMMENT '实际总流量(用于回测)',
    `predicted_vehicle` INT NOT NULL DEFAULT 0 COMMENT '预测车辆数',
    `predicted_pedestrian` INT NOT NULL DEFAULT 0 COMMENT '预测行人数',
    `mae` DOUBLE NULL COMMENT '平均绝对误差',
    `rmse` DOUBLE NULL COMMENT '均方根误差',
    `mape` DOUBLE NULL COMMENT '平均绝对百分比误差(%)',
    `confidence_interval_low` DOUBLE NULL COMMENT '95%置信下界',
    `confidence_interval_high` DOUBLE NULL COMMENT '95%置信上界',
    `created_at` DATETIME(6) NOT NULL COMMENT '预测生成时间',
    `created_by_id` BIGINT NULL COMMENT '预测者ID',
    CONSTRAINT `fk_pred_user` FOREIGN KEY (`created_by_id`) REFERENCES `users_user` (`id`) ON DELETE SET NULL,
    INDEX `idx_pred_time_loc` (`prediction_time`, `location`),
    INDEX `idx_pred_model` (`model_type`),
    INDEX `idx_pred_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='预测结果存储表';

-- ============================================================
-- 4. 模型管理模块
-- ============================================================

-- 4.1 已训练模型记录表
CREATE TABLE IF NOT EXISTS `prediction_trainedmodel` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '模型ID',
    `name` VARCHAR(100) NOT NULL COMMENT '模型名称',
    `model_type` VARCHAR(20) NOT NULL COMMENT '模型类型: lstm/cnn/lstm_cnn/collaborative',
    `version` VARCHAR(50) NOT NULL COMMENT '版本号',
    `status` VARCHAR(20) NOT NULL DEFAULT 'training' COMMENT '状态: training/completed/failed/deployed',
    `file_path` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '模型文件路径',
    -- 训练参数
    `epochs` INT NOT NULL DEFAULT 50 COMMENT '训练轮次',
    `batch_size` INT NOT NULL DEFAULT 32 COMMENT '批次大小',
    `learning_rate` DOUBLE NOT NULL DEFAULT 0.001 COMMENT '学习率',
    `sequence_length` INT NOT NULL DEFAULT 24 COMMENT '输入序列长度',
    -- 性能指标
    `train_loss` DOUBLE NULL COMMENT '训练集损失',
    `val_loss` DOUBLE NULL COMMENT '验证集损失',
    `mae` DOUBLE NULL COMMENT 'MAE',
    `rmse` DOUBLE NULL COMMENT 'RMSE',
    `mape` DOUBLE NULL COMMENT 'MAPE(%)',
    `r2_score` DOUBLE NULL COMMENT 'R2决定系数',
    `training_time` DOUBLE NULL COMMENT '训练耗时(秒)',
    -- 元信息
    `description` LONGTEXT NOT NULL COMMENT '模型描述',
    `created_by_id` BIGINT NULL COMMENT '创建者ID',
    `created_at` DATETIME(6) NOT NULL COMMENT '创建时间',
    `updated_at` DATETIME(6) NOT NULL COMMENT '更新时间',
    CONSTRAINT `fk_model_user` FOREIGN KEY (`created_by_id`) REFERENCES `users_user` (`id`) ON DELETE SET NULL,
    INDEX `idx_model_type` (`model_type`),
    INDEX `idx_model_status` (`status`),
    INDEX `idx_model_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='已训练模型记录表';

-- 4.2 模型训练日志表
CREATE TABLE IF NOT EXISTS `prediction_traininglog` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '日志ID',
    `model_id` BIGINT NOT NULL COMMENT '所属模型ID',
    `epoch` INT NOT NULL COMMENT '当前轮次',
    `train_loss` DOUBLE NOT NULL COMMENT '训练损失',
    `val_loss` DOUBLE NULL COMMENT '验证损失',
    `learning_rate` DOUBLE NOT NULL COMMENT '当前学习率',
    `timestamp` DATETIME(6) NOT NULL COMMENT '记录时间',
    CONSTRAINT `fk_log_model` FOREIGN KEY (`model_id`) REFERENCES `prediction_trainedmodel` (`id`) ON DELETE CASCADE,
    INDEX `idx_log_model` (`model_id`),
    INDEX `idx_log_epoch` (`model_id`, `epoch`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型训练日志表';

-- ============================================================
-- 5. 报告管理模块
-- ============================================================

CREATE TABLE IF NOT EXISTS `reports_report` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '报告ID',
    `title` VARCHAR(200) NOT NULL COMMENT '报告标题',
    `report_type` VARCHAR(20) NOT NULL COMMENT '报告类型: prediction/analysis/model_eval/summary',
    `format` VARCHAR(10) NOT NULL COMMENT '文件格式: pdf/excel/word',
    `file_path` VARCHAR(100) NOT NULL COMMENT '报告文件路径',
    `description` LONGTEXT NOT NULL COMMENT '报告描述',
    `date_from` DATE NULL COMMENT '数据起始日期',
    `date_to` DATE NULL COMMENT '数据结束日期',
    `file_size` INT NOT NULL DEFAULT 0 COMMENT '文件大小(bytes)',
    `created_by_id` BIGINT NULL COMMENT '创建者ID',
    `created_at` DATETIME(6) NOT NULL COMMENT '创建时间',
    CONSTRAINT `fk_report_user` FOREIGN KEY (`created_by_id`) REFERENCES `users_user` (`id`) ON DELETE SET NULL,
    INDEX `idx_report_type` (`report_type`),
    INDEX `idx_report_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告管理表';

-- ============================================================
-- 6. Django内置所需表（由migrate自动创建，此处仅列出关键表）
-- ============================================================
-- django_migrations        -- 迁移记录表
-- django_content_type      -- 内容类型表
-- auth_permission           -- 权限表
-- auth_group                -- 用户组表
-- auth_group_permissions    -- 组-权限关联表
-- users_user_groups         -- 用户-组关联表
-- users_user_user_permissions -- 用户-权限关联表
-- django_admin_log          -- 管理后台操作日志
-- django_session            -- 会话表

-- ============================================================
-- 初始化完成提示
-- ============================================================
SELECT '数据库 smart_traffic 初始化完成!' AS message;
