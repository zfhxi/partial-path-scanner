from clouddrive import CloudDriveClient
from celery import Celery


class FlaskCloudDrive2Wrapper(object):
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def connect_fs(self):
        self.fs = CloudDriveClient(self.host, self.username, self.password).fs

    def init_app(self, app):
        self.host = app.config['CLOUDDRIVE2_HOST']
        self.username = app.config['CLOUDDRIVE2_USERNAME']
        self.password = app.config['CLOUDDRIVE2_PASSWORD']
        self.connect_fs()
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['clouddrive2'] = self

    def attr(self, *args, **kwargs):
        return self.fs.attr(*args, **kwargs)

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
