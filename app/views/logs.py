import os
import time
from flask import render_template, Blueprint, request, jsonify, send_file, current_app, Response, stream_with_context
from flask_login import login_required
from app.utils import getLogger

logger = getLogger(__name__)
logs_bp = Blueprint('logs_bp', __name__, url_prefix='/logs')


@logs_bp.route('/', methods=['GET', 'POST'])
@login_required
def logs_index():
    return render_template('/logs/logs.html')


def _process_line(line):
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
    return f'<p class="log-line" style="color:{color}"> {line} </p>'


global_line_number = 0


@stream_with_context
def generate():
    global global_line_number
    fullname = os.path.join(current_app.config['LOG_DIR'], 'app.log')
    with open(fullname, 'r') as f:
        lines = f.readlines()[global_line_number:]
        for line in lines:
            global_line_number += 1
            context = _process_line(line)
            yield f"data:{context}\n\n"
            time.sleep(0.1)


@logs_bp.route("/get/", methods=['POST', 'GET'])
@login_required
def logs_get():
    global global_line_number
    fullname = os.path.join(current_app.config['LOG_DIR'], 'app.log')
    if request.method == 'POST':
        global_line_number = 0
        context = ''
        with open(fullname) as f:
            lines = f.readlines()
            for line in lines:
                global_line_number += 1
                context += _process_line(line) + '\n'
        return jsonify({"data": context, "position": str(global_line_number)})
    else:
        return Response(generate(), mimetype='text/event-stream')


@logs_bp.route('/download/', methods=['GET', 'POST'])
@login_required
def logs_download():
    fullname = os.path.join(current_app.config['LOG_DIR'], 'app.log')
    return send_file(f'/{fullname}')


@logs_bp.route('/')
@login_required
def logs():
    return render_template('/logs/logs.html')
