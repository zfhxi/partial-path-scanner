import os
from flask import Flask
from app.models import LoginUser
from app.extensions import redis_db, sqlite_db, login_manager, bcrypt, scheduler, cd2
from app.views import auth_bp, monitor_bp, files_bp, index_bp, logs_bp
from app.database import User, MonitoredFolder
from app.utils import folder_scan, create_folder_scheduler, getLogger
from celery import Celery, Task
from app.config import DevConfig, ProductionConfig

logger = getLogger("app_init")

FLASK_DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'
if FLASK_DEBUG:
    cfg = DevConfig()
else:
    cfg = ProductionConfig()


def create_app():
    flask_app = Flask(
        __name__,
        template_folder=os.path.join(cfg.APP_DIR, 'templates'),
        static_folder=os.path.join(cfg.APP_DIR, 'static'),
    )
    # 加载配置
    flask_app.config.from_object(cfg)

    # 注册扩展
    register_extensions(flask_app)

    # 注册蓝图
    register_blueprints(flask_app)

    # 注册 Celery
    # app.extensions['celery'] = make_celery(app)
    # celery.set_default()
    celery_app = celery_init_app(flask_app)

    # 初始化配置
    with flask_app.app_context():
        register_default_user(flask_app)
        init_launch(flask_app)

    return flask_app, celery_app


# 所有插件注册
def register_extensions(app):
    login_manager.init_app(app)
    # 设置登录端点
    login_manager.login_view = 'auth.login'

    sqlite_db.init_app(app)
    with app.app_context():
        sqlite_db.create_all()
    # redis_db.init_app(app, charset="utf-8", decode_responses=True)
    redis_db.init_app(app, decode_responses=True)
    bcrypt.init_app(app)

    # 注册定时任务调度器
    scheduler.init_app(app)
    scheduler.start()
    # 注册clouddrive2
    cd2.init_app(app)
    # 注册celery
    # celery_wrapper.init_app(app)


# 所有蓝图注册
def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(monitor_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(index_bp)
    app.register_blueprint(logs_bp)


# 注册一个默认用户
def register_default_user(app):
    username = app.config['FLASK_USERNAME']
    password = app.config['FLASK_PASSWORD']
    # 先删除数据库中的用户username
    # User.query.filter(User.username == username).delete()
    User.query.delete()

    # 再添加默认用户，参考https://foofish.net/flask-bcrypt.html
    user = User(username=username, password=password)
    sqlite_db.session.add(user)
    sqlite_db.session.commit()


# 初始化启动
def init_launch(app):
    fetch_mtime_only = app.config['UPDATE_MTIME_ON_STARTUP']
    fetch_all_mode = app.config['UPDATE_MTIME_OF_ALL']
    monitored_folders = MonitoredFolder.query.all()
    # folders = [result.folder for result in results]
    if fetch_mtime_only and not fetch_all_mode:
        logger.warning(f"正在获取缺失的目录mtime...")
    elif fetch_mtime_only and fetch_all_mode:
        logger.warning(f"正在刷新所有目录的mtime...")
    else:
        # logger.warning(f"启动时不更新目录的mtime...")
        pass
    servers_cfg = app.config['MEDIA_SERVERS']
    for _monitor in monitored_folders:
        if fetch_mtime_only:
            folder_scan(
                _monitor.folder,
                _monitor.blacklist,
                servers_cfg=servers_cfg,
                fs=cd2.fs,
                db=redis_db,
                fetch_mtime_only=fetch_mtime_only,
                fetch_all_mode=fetch_all_mode,
            )
        create_folder_scheduler(
            _monitor,
            servers_cfg=servers_cfg,
            scheduler=scheduler,
            fs=cd2.fs,
            db=redis_db,
            fetch_mtime_only=fetch_mtime_only,
            fetch_all_mode=fetch_all_mode,
        )


@login_manager.user_loader
def load_user(user_id):
    return LoginUser(user_id)


# 参考：https://flask.palletsprojects.com/en/stable/patterns/celery/
def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    # celery_app.conf.update(
    #     broker_url=app.config["CELERY_BROKER_URL"],
    #     result_backend=app.config["CELERY_RESULT_BACKEND"],
    # )
    celery_app.conf.update(
        worker_concurrency=4,
        task_ignore_result=False,
        task_track_started=True,
    )  # refer to https://github.com/Ryuchen/Panda-Sandbox/blob/09ae5da4b0ee4c688311208ce819dae82593490a/sandbox/celery.py#L43
    celery_app.autodiscover_tasks()
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app


flask_app, celery_app = create_app()
