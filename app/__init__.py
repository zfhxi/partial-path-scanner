import os
from flask import Flask
from flask_cors import CORS
from app.models import LoginUser
from app.extensions import redis_db, sqlite_db, login_manager, bcrypt, scheduler, storage_client, fc_handler, limiter
from app.views import auth_bp, monitor_bp, files_bp, index_bp, logs_bp
from app.database import User, MonitoredFolder
from app.utils import folder_scan, create_folder_scheduler, getLogger, setLogger
from celery import Celery, Task
from celery.signals import after_setup_logger
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

    # 跨域
    CORS(flask_app)

    # 打印程序启动提示信息
    logger.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    logger.warning("程序启动中......")
    logger.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
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
    # 注册存储客户端
    storage_client.init_app(app)
    # 注册celery
    # celery_wrapper.init_app(app)
    # 注册文件变更处理器
    fc_handler.init_app(app)
    # 注册请求频率限制
    limiter.init_app(app)


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
                storage_client=storage_client,
                db=redis_db,
                fetch_mtime_only=fetch_mtime_only,
                fetch_all_mode=fetch_all_mode,
            )
        create_folder_scheduler(
            _monitor,
            servers_cfg=servers_cfg,
            scheduler=scheduler,
            storage_client=storage_client,
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
    celery_app.conf.update(
        # worker_concurrency=4,
        broker_transport_options={
            'max_retries': 5,
            'interval_start': 0,
            'interval_step': 10,
            'interval_max': 30,
        },
    )
    celery_app.autodiscover_tasks()
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app


# celery日志配置
@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):
    logger = setLogger(logger, name="celery")


app, celery_app = create_app()
