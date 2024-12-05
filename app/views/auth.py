import datetime
from flask import Blueprint, request, redirect, render_template, flash, session, current_app
from flask_login import login_required, login_user, logout_user
from app.models import LoginUser
from app.database import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# 参考：https://github.com/HuTa0kj/flask-template/blob/main/app/views/user/user.py
# 登录
@auth_bp.route('/login/', methods=['GET', "POST"])
def login():
    if request.method == 'GET':
        return render_template('/auth/login.html')
    username = request.form.get('user')
    password = request.form.get('pwd')
    user = User.query.filter_by(username=username).first()
    is_valid = user and user.check_password(password)
    if is_valid:
        login_user(LoginUser(user.id))
        session.permanent = True
        current_app.permanent_session_lifetime = datetime.timedelta(days=7)
        return redirect('/')
    else:
        flash('用户名或密码输入错误', 'error')
        # return render_template('login.html', msg='用户名或密码输入错误')
        return render_template('/auth/login.html')


# 注册
"""
@user_blueprint.route("/register", method=["POST"])
def register():
    password = request.data.get("password")
    username = request.data.get("username")
    user = User(username=username)
    user.password = password
    sqlite_db.session.add(user)
    sqlite_db.session.commit()
"""


# 注销
@auth_bp.route('/logout/')
@login_required
def logout():
    logout_user()
    # 刷新页面的时候，做重定向，不要直接修改
    response = redirect('/')
    return response
