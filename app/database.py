from app.extensions import sqlite_db
from app.extensions import bcrypt
from app.utils import Json


# refer to https://foofish.net/flask-bcrypt.html
class User(sqlite_db.Model):
    __tablename__ = "user"
    # 主键、自增长
    id = sqlite_db.Column(sqlite_db.Integer, primary_key=True, autoincrement=True)
    username = sqlite_db.Column(sqlite_db.String(100), nullable=False, unique=True)
    password_hash = sqlite_db.Column(sqlite_db.String(100), nullable=False)

    def __init__(self, username, password, is_active=True):
        self.username = username
        self.password = password
        self.is_active = is_active

    @property
    def password(self):
        raise AttributeError('password: write-only field')

    @password.setter
    def password(self, pwd_value):
        # 用来保存密码hash值
        self.password_hash = bcrypt.generate_password_hash(pwd_value).decode('utf-8')

    def check_password(self, inp_value) -> bool:
        # 判断传过来的密码是否与数据库存的密码一致
        return bcrypt.check_password_hash(self.password_hash, inp_value)


class MonitoredFolder(sqlite_db.Model):
    __tablename__ = "monitored_folder"
    folder = sqlite_db.Column(sqlite_db.String(100), primary_key=True)
    enabled = sqlite_db.Column(sqlite_db.Boolean, default=True)
    blacklist = sqlite_db.Column(Json(1000), default='[]')
    interval = sqlite_db.Column(sqlite_db.String(100), default='1 day')
    offset = sqlite_db.Column(sqlite_db.Float, default=0)
