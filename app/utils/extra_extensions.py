from clouddrive import CloudDriveClient, CloudDriveFileSystem
from celery import Celery
from alist import AlistClient, AlistFileSystem
from threading import Timer
import time
import os
import json
import urllib3
from .logger import getLogger

logger = getLogger(__name__)


class FlaskStorageClientWrapper(object):
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def connect_fs(self):
        if self.provider == 'clouddrive2':
            self.client = CloudDriveClient(self.host, self.username, self.password)
            self.fs = CloudDriveFileSystem(self.client)
        elif self.provider == 'alist':
            self.client = AlistClient(self.host, self.username, self.password)
            self.fs = AlistFileSystem(self.client)
        else:
            raise NotImplementedError(f"The function connect_fs not implemented for provider {self.provider}")
        logger.info(f"已连接到{self.provider}[{self.host}]！")

    def init_app(self, app):
        self.provider = app.config['STORAGE_PROVIDER']
        self.host = app.config['STORAGE_HOST']
        self.username = app.config['STORAGE_USERNAME']
        self.password = app.config['STORAGE_PASSWORD']
        self.connect_fs()
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['storage_client'] = self

    def attr(self, *args, **kwargs):
        try:
            return self.fs.attr(*args, **kwargs)
        except OSError as e:
            if "Failed to connect to remote host" in str(e):
                self.connect_fs()
                return self.fs.attr(*args, **kwargs)
            else:
                raise OSError(e)

    def is_dir(self, *args, **kwargs):
        if self.provider == 'clouddrive2':
            return self.attr(*args, **kwargs)['isDirectory']
        elif self.provider == 'alist':
            return self.attr(*args, **kwargs)['is_dir']
        else:
            raise NotImplementedError(f"The function is_dir not implemented for provider {self.provider}")

    def get_mtime(self, *args, **kwargs):
        return str(self.attr(*args, **kwargs)['mtime'])

    def walk_attr(self, *args, **kwargs):
        try:
            return self.fs.walk_attr(*args, **kwargs)
        except OSError as e:
            if "Failed to connect to remote host" in str(e):
                self.connect_fs()
                return self.fs.walk_attr(*args, **kwargs)
            else:
                raise OSError(e)

    def listdir_attr(self, *args, **kwargs):
        try:
            return self.fs.listdir_attr(*args, **kwargs)
        except OSError as e:
            if "Failed to connect to remote host" in str(e):
                self.connect_fs()
                return self.fs.listdir_attr(*args, **kwargs)
            else:
                raise OSError(e)

    def exists(self, *args, **kwargs):
        try:
            return self.fs.exists(*args, **kwargs)
        except OSError as e:
            if "Failed to connect to remote host" in str(e):
                self.connect_fs()
                return self.fs.exists(*args, **kwargs)
            else:
                raise OSError(e)


class FlaskCeleryWrapper(object):

    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        self._celery = self.make_celery(app)
        app.extensions['celery'] = self

    # 初始化 Celery
    def make_celery(app):
        # 使用Flask应用的配置初始化Celery
        celery = Celery(app.import_name)
        celery.conf.update(
            broker_url=app.config["CELERY_BROKER_URL"],
            result_backend=app.config["CELERY_RESULT_BACKEND"],
        )
        # 自动发现任务
        celery.autodiscover_tasks(['app.tasks'])

        class ContextTask(celery.Task):
            """为 Celery 任务提供 Flask 应用上下文"""

            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        # 设置 Celery 使用应用上下文任务
        celery.Task = ContextTask
        return celery


# cd2 webhook变动处理
# refer to https://github.com/tanlidoushen/CloudDriveAlistEmbyScripts/blob/main/webhook_strm/webhook%E7%9B%91%E6%8E%A7-strm.py
class FlaskFileChangeHandlerWrapper(object):
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.init_handler(app)
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['filechangehandler'] = self

    def init_handler(self, app):
        self.wait_time = int(app.config['FC_HANDLER_TIMER_INTERVAL'])  # 等待时间（秒）
        self.dest_filepool = []  # 用于存储路径信息列表
        self.src_filepool = []
        self.last_event_time = 0  # 上一次事件的时间戳
        self.dest_timer = None  # 定时器
        self.src_timer = None

        # 配置可处理的文件后缀和关键词
        self.allowed_extensions = app.config['FC_HANDLER_ALLOWED_EXTS']
        self.allowed_keywords = app.config['FC_HANDLER_ALLOWED_PATH_KEYWORDS']
        self.sync_other_device_enabled = app.config['FC_HANDLER_SYNC_OTHER_DEVICE_ENABLED']
        if self.sync_other_device_enabled:
            self.sync_other_device_url = app.config['FC_HANDLER_SYNC_OTHER_DEVICE_URL']
            self.sync_other_device_headers = {"Content-Type": "application/json; charset=UTF-8"}
            self.http = urllib3.PoolManager()

    def reset_dest_timer(self, _func):
        if self.dest_timer:
            self.dest_timer.cancel()
        self.dest_timer = Timer(self.wait_time, self.process_dest_changes, (_func,))
        self.dest_timer.start()

    def reset_src_timer(self, _func):
        if self.src_timer:
            self.src_timer.cancel()
        self.src_timer = Timer(self.wait_time, self.process_src_changes, (_func,))
        self.src_timer.start()

    def add_change(self, path, _func, src_file_flag=False):
        # 过滤文件后缀
        if not self._is_valid_file(path):
            return

        # 提取目录部分
        # dir_path = os.path.dirname(path)
        # 记录路径（避免重复）
        # if dir_path not in self.changedfile_pool:
        # self.changedfile_pool.append(dir_path)
        if src_file_flag:
            if path not in self.src_filepool:
                self.src_filepool.append(path)
            self.reset_src_timer(_func)
        else:
            if path not in self.dest_filepool:
                self.dest_filepool.append(path)
            self.reset_dest_timer(_func)
        self.last_event_time = time.time()

    def process_dest_changes(self, _func):
        if len(self.dest_filepool) == 0:
            return

        _func(self.dest_filepool)
        # 清空记录
        self.dest_filepool.clear()

    def process_src_changes(self, _func):
        if len(self.src_filepool) == 0:
            return

        _func(self.src_filepool)
        # 清空记录
        self.src_filepool.clear()

    def _is_valid_file(self, path):
        """
        判断路径是否满足后缀和关键词要求
        """
        if not any(keyword in path for keyword in self.allowed_keywords):
            return False
        # FIXME: 通过splitext来粗略判断是否为文件夹，并不能百分百准确
        ext = os.path.splitext(path)[1]
        if ext == '' or ext not in self.allowed_extensions:  # 是文件夹
            return True
        return ext.lower() in self.allowed_extensions

    def sync_filechange_to_other_device(self, upstream_url, payload):
        if self.sync_other_device_enabled:
            try:
                self.http.request(
                    'POST',
                    self.sync_other_device_url,
                    body=json.dumps(payload).encode('utf-8'),
                    headers=self.sync_other_device_headers,
                )
                return f"已同步请求到其他设备：{self.sync_other_device_url}！"
            except Exception as e:
                return f"同步请求到其他设备失败，url: {self.sync_other_device_url}！ Error: {e}"
        else:
            return None

    @staticmethod
    def translate_action(action, source_file, destination_file):
        """
        翻译文件操作类型，并区分“移动”和“重命名”
        """
        if action == "rename":
            source_dir = os.path.dirname(source_file)
            dest_dir = os.path.dirname(destination_file)
            if source_dir != dest_dir:
                return "移动"
            else:
                return "重命名"
        translations = {"create": "创建", "delete": "删除"}
        return translations.get(action, "未知操作")
