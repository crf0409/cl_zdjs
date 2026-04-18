"""
Django settings for traffic_prediction project.
智能交通流量预测系统 - 项目配置
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR.parent

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-traffic-prediction-dev-key-change-in-production'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'corsheaders',
    # Local apps
    'apps.users',
    'apps.traffic_data',
    'apps.prediction',
    'apps.visualization',
    'apps.monitoring',
    'apps.api',
    'apps.reports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'traffic_prediction.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'traffic_prediction.wsgi.application'

# Database - 支持 SQLite(开发) 和 MySQL(生产) 两种模式
# 通过环境变量 DB_ENGINE=mysql 切换到 MySQL
if os.environ.get('DB_ENGINE') == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('MYSQL_DATABASE', 'smart_traffic'),
            'USER': os.environ.get('MYSQL_USER', 'traffic_user'),
            'PASSWORD': os.environ.get('MYSQL_PASSWORD', 'traffic_pass_2024'),
            'HOST': os.environ.get('MYSQL_HOST', '127.0.0.1'),
            'PORT': os.environ.get('MYSQL_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'users.User'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
}

CORS_ALLOW_ALL_ORIGINS = True

# ML Model storage
MODEL_STORAGE_DIR = BASE_DIR / 'media' / 'models'

# Optional external data paths. They can be overridden on a new machine by
# setting NUSCENES_DATA_DIR / YOLO_RESULTS_DIR in the environment.
NUSCENES_DATA_DIR = Path(
    os.environ.get(
        'NUSCENES_DATA_DIR',
        WORKSPACE_DIR / 'project2_centerpoint' / 'nuscenes_data' / 'nuScenes-mini-val',
    )
)
YOLO_RESULTS_DIR = Path(
    os.environ.get(
        'YOLO_RESULTS_DIR',
        WORKSPACE_DIR / 'project1_yolo_obstacle' / 'results',
    )
)

LOGIN_URL = '/users/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/users/login/'
