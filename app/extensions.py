from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_apscheduler import APScheduler


from app.utils import FlaskCloudDrive2Wrapper


sqlite_db = SQLAlchemy()
redis_db = FlaskRedis()
login_manager = LoginManager()
scheduler = APScheduler()
bcrypt = Bcrypt()
cd2 = FlaskCloudDrive2Wrapper()
# celery_wrapper = FlaskCeleryWrapper()
