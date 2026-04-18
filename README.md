# 智能交通流量预测系统

> 基于深度学习的智能驾驶感知与交通流量预测平台，融合 CenterPoint 3D目标检测 与 LSTM/CNN 时序预测模型。

## 项目结构

```
smart_traffic_system/
├── README.md                          # 本文档 - 部署运行说明
├── docker-compose.yml                 # Docker 一键启动配置
├── .env.example                       # 环境变量模板
│
├── project3_traffic_prediction/       # [后端+前端] Django 交通流量预测 Web 系统
│   ├── Dockerfile                     # 后端容器构建文件
│   ├── manage.py                      # Django 管理入口
│   ├── requirements.txt               # Python 依赖
│   ├── init_data.py                   # 数据初始化脚本
│   ├── traffic_prediction/            # Django 项目配置
│   │   ├── settings.py                # 主配置 (支持 SQLite/MySQL 切换)
│   │   ├── urls.py                    # URL 路由
│   │   └── wsgi.py                    # WSGI 入口
│   ├── apps/                          # 业务模块 (7个Django App)
│   │   ├── users/                     #   用户认证与权限管理
│   │   ├── traffic_data/              #   交通数据管理 (CRUD)
│   │   ├── prediction/                #   模型训练与预测
│   │   ├── visualization/             #   数据可视化仪表盘
│   │   ├── monitoring/                #   系统监控
│   │   ├── api/                       #   RESTful API (DRF)
│   │   └── reports/                   #   报告生成
│   ├── ml_models/                     # 机器学习模型实现
│   │   ├── lstm_model.py              #   LSTM 时序预测模型
│   │   ├── cnn_model.py               #   CNN + Hybrid CNN-LSTM 模型
│   │   └── collaborative_filter.py    #   协同过滤推荐模型
│   ├── templates/                     # 前端 HTML 模板 (26个页面)
│   ├── static/                        # 前端静态资源 (CSS/JS/IMG)
│   └── utils/                         # 工具函数
│
├── project2_centerpoint/              # [感知模块] CenterPoint 3D目标检测
│   ├── CenterPoint/                   # CenterPoint 核心代码
│   │   ├── det3d/                     #   检测库 (模型/数据集/训练)
│   │   ├── tools/                     #   训练/推理/跟踪脚本
│   │   ├── configs/                   #   模型配置文件
│   │   └── requirements.txt           #   依赖
│   └── nuscenes_data/                 # nuScenes 迷你验证集
│
└── database/                          # 数据库文件
    ├── init_database.sql              # MySQL 建库建表脚本
    ├── init_data.sql                  # 初始数据脚本
    ├── database_design.md             # 数据库设计文档 + ER图
    └── mysql/my.cnf                   # MySQL 配置
```

## 环境要求

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.9 ~ 3.11 | 推荐 3.11 |
| MySQL | 8.0+ | 生产环境；开发可用 SQLite |
| Node.js | 无需安装 | 前端使用 Django 模板 + CDN |
| Docker | 20.10+ | 容器化部署 |
| Docker Compose | 2.0+ | 编排服务 |
| CUDA | 11.x+ | 仅 CenterPoint 模块需要 (可选) |
| TensorFlow | 2.13.x | ML 模型训练/推理 |

## 快速开始

### 方式一：Docker 一键部署（推荐）

```bash
# 1. 克隆/解压项目
cd smart_traffic_system/

# 2. 创建环境变量文件
cp .env.example .env
# 按需修改 .env 中的数据库密码等配置

# 3. 一键启动 (MySQL + Django)
docker-compose up -d

# 4. 查看启动日志
docker-compose logs -f web

# 5. 初始化示例数据 (首次启动后执行)
docker-compose exec web python init_data.py

# 6. 访问系统
#    主页:  http://localhost:8000
#    后台:  http://localhost:8000/admin/
#    API:   http://localhost:8000/api/v1/
```

**默认账户：**

| 角色 | 用户名 | 密码 | 权限 |
|------|--------|------|------|
| 管理员 | admin | admin123 | 全部功能 |
| 分析师 | analyst | analyst123 | 模型训练、预测、报告 |
| 普通用户 | user1 | user123 | 查看数据和结果 |

### 方式二：本地运行（开发模式，使用 SQLite）

```bash
# 1. 进入后端目录
cd project3_traffic_prediction/

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# 3. 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 4. 数据库迁移（自动使用 SQLite）
python manage.py migrate

# 5. 初始化示例数据（创建用户+导入交通数据）
python init_data.py

# 6. 启动开发服务器
python manage.py runserver 0.0.0.0:8000

# 7. 浏览器访问 http://localhost:8000
```

### 方式三：本地运行 + MySQL

```bash
# 1. 确保 MySQL 8.0 已安装并启动

# 2. 创建数据库
mysql -u root -p < database/init_database.sql

# 3. 设置环境变量
export DB_ENGINE=mysql
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_DATABASE=smart_traffic
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password

# 4. 安装依赖 (同方式二的步骤 1~3)
cd project3_traffic_prediction/
pip install -r requirements.txt

# 5. 迁移 + 初始化数据
python manage.py migrate
python init_data.py

# 6. 启动
python manage.py runserver 0.0.0.0:8000
```

## 功能模块说明

### 后端功能 (Django)

| 模块 | URL | 功能 |
|------|-----|------|
| 仪表盘 | `/` | 交通流量总览、实时数据展示 |
| 用户管理 | `/users/` | 注册、登录、角色管理、活动日志 |
| 数据管理 | `/traffic/` | 流量数据上传、查询、清洗、质量评估 |
| 模型管理 | `/prediction/` | LSTM/CNN/Hybrid 模型训练、对比、部署 |
| 可视化 | `/visualization/` | 流量趋势图、热力图、模型对比 |
| 系统监控 | `/monitoring/` | CPU/内存/GPU 状态、模型运行监控 |
| 报告中心 | `/reports/` | PDF/Excel/Word 报告自动生成 |
| REST API | `/api/v1/` | 完整 CRUD API，支持第三方接入 |
| 管理后台 | `/admin/` | Django Admin 数据库管理 |

### ML 模型

| 模型 | 文件 | 说明 | 最优指标 |
|------|------|------|---------|
| LSTM | `ml_models/lstm_model.py` | 长短期记忆网络，捕捉时序依赖 | R²=0.923 |
| CNN | `ml_models/cnn_model.py` | 1D卷积，提取局部时序特征 | R²=0.935 |
| Hybrid | `ml_models/cnn_model.py` | CNN+LSTM 混合，最优性能 | R²=0.951 |
| 协同过滤 | `ml_models/collaborative_filter.py` | 基于相似性的模式推荐 | R²=0.887 |

### CenterPoint 3D 感知模块

用于从 nuScenes 点云数据中进行 3D 目标检测（车辆、行人、自行车等），为交通流量系统提供感知数据源。

```bash
# CenterPoint 环境搭建 (需要 GPU + CUDA)
cd project2_centerpoint/CenterPoint/
pip install -r requirements.txt
bash setup.sh   # 编译 CUDA 扩展

# 推理演示
python tools/demo.py
```

## 数据库

- **建库建表脚本：** `database/init_database.sql`
- **初始数据脚本：** `database/init_data.sql`
- **设计文档+ER图：** `database/database_design.md`
- **Django 自动生成的 SQLite：** `project3_traffic_prediction/db.sqlite3` (开发模式)

共 9 张业务表，详见 `database/database_design.md`。

## API 接口

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/traffic/` | 查询交通流量数据 (分页+筛选) |
| POST | `/api/v1/traffic/` | 新增交通数据 |
| GET | `/api/v1/predictions/` | 查询预测结果 |
| GET | `/api/v1/models/` | 查询已训练模型 |
| POST | `/api/v1/predict/` | 执行在线预测 |

所有 API 需要认证，使用 Django Session 或 Token 认证。

## 常用命令

```bash
# Docker 相关
docker-compose up -d          # 启动
docker-compose down           # 停止
docker-compose logs -f web    # 查看日志
docker-compose exec web bash  # 进入容器

# Django 管理
python manage.py migrate              # 数据库迁移
python manage.py createsuperuser      # 创建管理员
python manage.py collectstatic        # 收集静态文件
python init_data.py                   # 初始化示例数据

# 测试 ML 模型
python ml_models/lstm_model.py        # 测试 LSTM
python ml_models/cnn_model.py         # 测试 CNN + Hybrid
python ml_models/collaborative_filter.py  # 测试协同过滤
```

## 技术栈

**后端：** Django 4.2 + Django REST Framework + TensorFlow 2.13 + MySQL 8.0

**前端：** Django Templates + Bootstrap 5.3 + ECharts (CDN)

**感知：** CenterPoint + PyTorch + nuScenes + spconv

**部署：** Docker + Docker Compose
