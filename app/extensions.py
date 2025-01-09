from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_apscheduler import APScheduler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


from app.utils import FlaskStorageClientWrapper, FlaskFileChangeHandlerWrapper


sqlite_db = SQLAlchemy()
redis_db = FlaskRedis()
login_manager = LoginManager()
scheduler = APScheduler()
bcrypt = Bcrypt()
storage_client = FlaskStorageClientWrapper()
fc_handler = FlaskFileChangeHandlerWrapper()
limiter = Limiter(key_func=get_remote_address)
