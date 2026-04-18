-- ============================================================
-- 智能交通流量预测系统 - 初始数据导入脚本
-- 功能：插入管理员账户、示例数据
-- 注意：密码使用Django PBKDF2哈希，默认密码见注释
-- ============================================================

USE smart_traffic;

-- ============================================================
-- 1. 创建初始用户
-- ============================================================
-- 注意：以下密码哈希对应明文密码，实际部署时请修改
-- 推荐使用 python manage.py createsuperuser 创建管理员
-- 或运行 python init_data.py 自动初始化

-- 管理员: admin / admin123
INSERT INTO `users_user` (
    `password`, `is_superuser`, `username`, `email`, `is_staff`, `is_active`,
    `date_joined`, `role`, `phone`, `department`, `created_at`, `updated_at`
) VALUES (
    'pbkdf2_sha256$600000$placeholder$hash_admin123',
    1, 'admin', 'admin@traffic.com', 1, 1,
    NOW(), 'admin', '13800000001', '系统管理部', NOW(), NOW()
);

-- 数据分析师: analyst / analyst123
INSERT INTO `users_user` (
    `password`, `is_superuser`, `username`, `email`, `is_staff`, `is_active`,
    `date_joined`, `role`, `phone`, `department`, `created_at`, `updated_at`
) VALUES (
    'pbkdf2_sha256$600000$placeholder$hash_analyst123',
    0, 'analyst', 'analyst@traffic.com', 0, 1,
    NOW(), 'analyst', '13800000002', '数据分析部', NOW(), NOW()
);

-- 普通用户: user1 / user123
INSERT INTO `users_user` (
    `password`, `is_superuser`, `username`, `email`, `is_staff`, `is_active`,
    `date_joined`, `role`, `phone`, `department`, `created_at`, `updated_at`
) VALUES (
    'pbkdf2_sha256$600000$placeholder$hash_user123',
    0, 'user1', 'user1@traffic.com', 0, 1,
    NOW(), 'user', '13800000003', '交通管理部', NOW(), NOW()
);

-- ============================================================
-- 2. 插入示例气象数据（7天）
-- ============================================================
INSERT INTO `traffic_data_weatherdata`
    (`timestamp`, `location`, `weather_type`, `temperature`, `humidity`, `wind_speed`, `visibility`, `precipitation`, `created_at`)
VALUES
    ('2024-01-20 08:00:00', 'CAM_FRONT_主干道A', 'sunny',   15.2, 45.0, 3.2, 15.0, 0.0, NOW()),
    ('2024-01-20 14:00:00', 'CAM_FRONT_主干道A', 'cloudy',  18.5, 52.0, 4.1, 12.0, 0.0, NOW()),
    ('2024-01-21 08:00:00', 'CAM_FRONT_主干道A', 'rainy',   12.0, 85.0, 5.5,  6.0, 8.5, NOW()),
    ('2024-01-21 14:00:00', 'CAM_FRONT_商业区B', 'rainy',   13.2, 82.0, 4.8,  7.0, 5.2, NOW()),
    ('2024-01-22 08:00:00', 'CAM_FRONT_商业区B', 'sunny',   16.8, 40.0, 2.5, 18.0, 0.0, NOW()),
    ('2024-01-22 14:00:00', 'CAM_FRONT_住宅区C', 'overcast',14.5, 65.0, 3.8, 10.0, 0.0, NOW()),
    ('2024-01-23 08:00:00', 'CAM_FRONT_住宅区C', 'foggy',   10.0, 92.0, 1.2,  2.5, 0.0, NOW());

-- ============================================================
-- 3. 插入示例时段标签
-- ============================================================
INSERT INTO `traffic_data_timeperiodlabel`
    (`date`, `period`, `day_type`, `holiday_name`, `is_event`, `event_name`, `flow_factor`, `created_at`)
VALUES
    ('2024-01-20', 'morning_peak', 'weekend',  '', 0, '', 0.8, NOW()),
    ('2024-01-20', 'daytime',      'weekend',  '', 0, '', 0.9, NOW()),
    ('2024-01-20', 'evening_peak', 'weekend',  '', 0, '', 0.85, NOW()),
    ('2024-01-20', 'night',        'weekend',  '', 0, '', 0.6, NOW()),
    ('2024-01-21', 'morning_peak', 'weekend',  '', 0, '', 0.75, NOW()),
    ('2024-01-22', 'morning_peak', 'workday',  '', 0, '', 1.0, NOW()),
    ('2024-01-22', 'evening_peak', 'workday',  '', 0, '', 1.0, NOW()),
    ('2024-01-23', 'morning_peak', 'workday',  '', 0, '', 1.0, NOW()),
    ('2024-02-10', 'morning_peak', 'holiday',  '春节', 0, '', 0.3, NOW()),
    ('2024-02-10', 'daytime',      'holiday',  '春节', 0, '', 0.4, NOW());

-- ============================================================
-- 4. 插入示例训练模型记录
-- ============================================================
INSERT INTO `prediction_trainedmodel`
    (`name`, `model_type`, `version`, `status`, `epochs`, `batch_size`,
     `learning_rate`, `sequence_length`, `train_loss`, `val_loss`,
     `mae`, `rmse`, `mape`, `r2_score`, `training_time`,
     `description`, `created_by_id`, `created_at`, `updated_at`)
VALUES
    ('LSTM交通流量预测v1', 'lstm', '1.0.0', 'deployed',
     50, 32, 0.001, 24, 0.0234, 0.0312,
     2.15, 3.42, 8.7, 0.923, 145.6,
     '基于LSTM的交通流量时序预测模型，使用nuScenes数据集训练', 1, NOW(), NOW()),
    ('CNN特征提取v1', 'cnn', '1.0.0', 'completed',
     30, 64, 0.0005, 12, 0.0189, 0.0278,
     1.98, 3.15, 7.9, 0.935, 89.3,
     'CNN模型用于交通数据空间特征提取', 1, NOW(), NOW()),
    ('LSTM+CNN混合模型v1', 'lstm_cnn', '1.0.0', 'deployed',
     80, 32, 0.0008, 24, 0.0156, 0.0223,
     1.67, 2.78, 6.5, 0.951, 267.8,
     'LSTM+CNN混合架构，结合时序特征与空间特征，性能最优', 1, NOW(), NOW()),
    ('协同过滤推荐v1', 'collaborative', '1.0.0', 'completed',
     20, 128, 0.01, 48, 0.0345, 0.0401,
     2.89, 4.12, 11.3, 0.887, 34.5,
     '基于协同过滤的交通模式推荐，利用相似路段历史模式预测', 1, NOW(), NOW());

-- ============================================================
-- 提示：完整的示例数据（交通流量等大量数据）
-- 建议通过 Django 脚本导入:
--   cd backend && python init_data.py
-- 该脚本会自动生成30天的模拟交通流量数据并导入数据库
-- ============================================================

SELECT '初始数据导入完成!' AS message;
SELECT CONCAT('用户数: ', COUNT(*)) AS info FROM users_user;
SELECT CONCAT('气象数据: ', COUNT(*)) AS info FROM traffic_data_weatherdata;
SELECT CONCAT('时段标签: ', COUNT(*)) AS info FROM traffic_data_timeperiodlabel;
SELECT CONCAT('训练模型: ', COUNT(*)) AS info FROM prediction_trainedmodel;
