import os
from flask import render_template, Blueprint, request, jsonify, send_file, current_app
from flask_login import login_required
from app.utils import getLogger

logger = getLogger(__name__)

logs_bp = Blueprint('logs_bp', __name__, url_prefix='/logs')


@logs_bp.route('/', methods=['GET', 'POST'])
@login_required
def logs_index():

    return render_template('/logs/logs.html')


# 参考：https://www.cnblogs.com/ydf0509/p/11032904.html
@logs_bp.route("/get/", methods=['POST', 'GET'])
@login_required
def logs_get():
    # fullname = os.path.dirname(os.path.abspath(__file__)) + '/app.log'
    fullname = os.path.join(current_app.config['LOG_DIR'], 'app.log')
    position = int(request.args.get('position'))
    # current_app.logger.debug(position)

    with open(fullname, 'rb') as f:
        try:
            f.seek(position, 0)
        except Exception as e:
            logger.warning(f"读取错误: {e}")
            f.seek(0, 0)
        lines = f.readlines()
        content_text = ''
        for line in lines:
            try:
                line = line.strip().decode()
            except Exception as e:
                logger.warning(f"decode错误: {e}")
                line = line.strip()
            if 'DEBUG' in line:
                color = '#00FF00'
            elif 'INFO' in line:
                color = '#000'
            elif 'WARNING' in line:
                color = '#c1bf78'
            elif 'ERROR' in line:
                color = '#FF0000'
            elif 'CRITICAL' in line:
                color = '#FF0033'
            else:
                color = ''
            content_text += f'<p class="log-line" style="color:{color}"> {line} </p>'

        # content_text = f.read().decode()
        # # nb_print([content_text])
        # content_text = content_text.replace('\n', '<br>')
        # # nb_print(content_text)
        position_new = f.tell()
        # current_app.logger.debug(position_new)
        # nb_print(content_text)
        print(f"position_new: {position_new}")

        return jsonify({"content_text": content_text, "position": str(position_new)})


@logs_bp.route('/download/', methods=['GET', 'POST'])
@login_required
def logs_download():
    fullname = os.path.join(current_app.config['LOG_DIR'], 'app.log')
    return send_file(f'/{fullname}')


@logs_bp.route('/')
@login_required
def logs():
    return render_template('/logs/logs.html')
