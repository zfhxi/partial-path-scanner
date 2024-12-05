import os
from app.utils import YAMLLoader, read_deepvalue, str2bool, dict2obj


app_dir = os.path.dirname(os.path.abspath(__file__))  # This directory
config_dir = os.path.join(app_dir, '../config/')
log_dir = os.path.join(app_dir, '../log/')


class BaseConfig(object):
    def __init__(self, yaml_path=None):
        self.APP_DIR = app_dir
        self.CONFIG_DIR = config_dir
        self.LOG_DIR = log_dir
        if yaml_path is not None:
            YAML_LOADER = YAMLLoader(yaml_path)
        else:
            YAML_LOADER = YAMLLoader(os.path.join(config_dir, 'config.yaml'))
        self._config = YAML_LOADER.get()
        # 配置加载
        self.DEBUG = False
        self.TESTING = False

        self.FLASK_HOST = read_deepvalue(self._config, 'flask', 'host')
        self.FLASK_PORT = int(read_deepvalue(self._config, 'flask', 'port'))
        self.SECRET_KEY = read_deepvalue(self._config, 'flask', 'secret_key')
        self.FLASK_USERNAME = read_deepvalue(self._config, 'flask', 'username')
        self.FLASK_PASSWORD = read_deepvalue(self._config, 'flask', 'password')
        # 数据库
        # Redis
        redis_host = read_deepvalue(self._config, 'databases', 'redis', 'host')
        redis_port = read_deepvalue(self._config, 'databases', 'redis', 'port')
        redis_username = read_deepvalue(self._config, 'databases', 'redis', 'username')
        redis_password = read_deepvalue(self._config, 'databases', 'redis', 'password')
        redis_db = read_deepvalue(self._config, 'databases', 'redis', 'db')
        self.REDIS_URL = f'redis://{redis_username}:{redis_password}@{redis_host}:{redis_port}/{redis_db}'
        self.REDIS_SOCKET_TIMEOUT = int(read_deepvalue(self._config, 'databases', 'redis', 'socket_timeout'))
        self.REDIS_CONNECTION_POOL = str2bool(read_deepvalue(self._config, 'databases', 'redis', 'pool_enabled'))
        # Celery
        celery_broker_db = read_deepvalue(self._config, 'databases', 'redis', 'celery_broker_db')
        celery_result_db = read_deepvalue(self._config, 'databases', 'redis', 'celery_result_db')
        self.CELERY_BROKER_URL = (
            f'redis://{redis_username}:{redis_password}@{redis_host}:{redis_port}/{celery_broker_db}'
        )
        self.CELERY_RESULT_BACKEND = (
            f'redis://{redis_username}:{redis_password}@{redis_host}:{redis_port}/{celery_result_db}'
        )
        self.CELERY_LOG_DIR = os.path.join(self.APP_DIR, '_celery_logs')
        self.CELERY = dict2obj(
            dict(
                broker_url=self.CELERY_BROKER_URL,
                result_backend=self.CELERY_RESULT_BACKEND,
                broker_connection_retry_on_startup=True,
                task_ignore_result=False,
                task_track_started=True,
                worker_pool_restarts=True,  # refer to https://github.com/celery/celery/issues/8966
                broker_heartbeat=10,
                broker_connection_timeout=15,
                broker_connection_retry=True,
                broker_connection_max_retries=200,
                worker_cancel_long_running_tasks_on_connection_loss=True,
                result_backend_always_retry=True,
                redis_backend_health_check_interval=10,
            )
        )
        # SQLAlchemy
        self.SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
            config_dir, read_deepvalue(self._config, 'databases', 'sqlite', 'path')
        )
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False  # 如果设置True,会消耗额外内存空间，它用于追踪对象修改并发送信号
        self.SQLALCHEMY_ECHO = False  # 调试设置为True
        self.SQLALCHEMY_POOL_TIMEOUT = int(read_deepvalue(self._config, 'databases', 'sqlite', 'pool_timeout'))
        self.SQLALCHEMY_POOL_SIZE = int(read_deepvalue(self._config, 'databases', 'sqlite', 'pool_size'))
        # 调度器
        self.SCHEDULER_TIMEZONE = read_deepvalue(self._config, 'flask', 'scheduler', 'timezone')
        self.SCHEDULER_API_ENABLED = str2bool(read_deepvalue(self._config, 'flask', 'scheduler', 'api_enabled'))
        self.SCHEDULER_DEFAULT_INTERVAL = read_deepvalue(self._config, 'flask', 'scheduler', 'default_interval')
        # clouddrive2
        self.CLOUDDRIVE2_HOST = read_deepvalue(self._config, 'clouddrive2', 'host')
        self.CLOUDDRIVE2_USERNAME = read_deepvalue(self._config, 'clouddrive2', 'username')
        self.CLOUDDRIVE2_PASSWORD = read_deepvalue(self._config, 'clouddrive2', 'password')
        self.MEDIA_SERVERS = read_deepvalue(self._config, 'media_servers')
        self.UPDATE_MTIME_ON_STARTUP = str2bool(os.getenv('UPDATE_MTIME_ON_STARTUP', 'False'))
        self.UPDATE_MTIME_OF_ALL = str2bool(os.getenv('UPDATE_MTIME_OF_ALL', 'False'))


class DevConfig(BaseConfig):
    def __init__(self, yaml_path=None):
        super().__init__(os.path.join(config_dir, 'config_dev.yaml'))
        self.DEBUG = True
        self.ENV = 'development'
        self.ASSETS_DEBUG = True
        self.WTF_CSRF_ENABLED = False


class ProductionConfig(BaseConfig):
    """生产环境"""

    def __init__(self, yaml_path=None):
        super().__init__(yaml_path)
        self.ENV = 'production'
