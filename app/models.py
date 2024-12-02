from flask_login import UserMixin


class LoginUser(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

    def get_id(self):
        return str(self.id)  # 返回id属性的字符串表示

    # def check_password(self, password):
    # return True

    def is_authenticated(self):
        return True  # 这里简单返回True，表示所有用户都已经通过了身份验证
