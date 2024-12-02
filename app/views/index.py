from flask import render_template, Blueprint, jsonify, current_app
from flask_login import login_required
from celery.result import AsyncResult

index_bp = Blueprint('index_bp', __name__, url_prefix='/')


@index_bp.route('/', methods=['GET', 'POST'])
@index_bp.route('/index/', methods=['GET', 'POST'])
@login_required
def index():
    scheduler_default_interval = current_app.config['SCHEDULER_DEFAULT_INTERVAL']
    return render_template('/monitor/index.html', scheduler_default_interval=scheduler_default_interval)


# 查询任务状态
@index_bp.route('/task_status/<task_id>', methods=['GET'])
@login_required
def get_task_status(task_id):
    task = AsyncResult(task_id)  # 查询任务结果
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Pending...',
        }
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'result': task.result,  # 返回任务的执行结果
        }
    else:
        response = {
            'state': task.state,
            'status': str(task.info),  # 若任务失败，返回异常信息
        }
    return jsonify(response)
