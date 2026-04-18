# ============================================================
# 智能交通流量预测系统 - 后端 Dockerfile
# 基于 Python 3.11 + Django 4.2
# ============================================================
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=traffic_prediction.settings

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 复制项目源码
COPY . .

# 收集静态文件
RUN python manage.py collectstatic --noinput 2>/dev/null || true

# 创建必要目录
RUN mkdir -p media/models media/reports staticfiles

# 暴露端口
EXPOSE 8000

# 启动命令: 先执行数据库迁移，再启动服务
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"]
