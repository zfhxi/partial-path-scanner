from clouddrive import CloudDriveClient, CloudDriveFileSystem
from celery import Celery
from alist import AlistClient, AlistFileSystem


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
        return self.fs.attr(*args, **kwargs)

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
        return self.fs.walk_attr(*args, **kwargs)

    def listdir_attr(self, *args, **kwargs):
        return self.fs.listdir_attr(*args, **kwargs)

    def exists(self, *args, **kwargs):
        return self.fs.exists(*args, **kwargs)


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
