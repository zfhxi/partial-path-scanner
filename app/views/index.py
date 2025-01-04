from flask import render_template, Blueprint, jsonify, current_app, request
from flask_login import login_required
from celery.result import AsyncResult
from app.extensions import fc_handler, storage_client, redis_db
from app.utils import getLogger, manual_scan_dest_pathlist, manual_scan_deleted_pathlist
from app.tasks import async_filechange_to_other_device
import functools
import os

logger = getLogger(__name__)
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


def add_change2fc_handler(action_cn, src_file, dest_file, src_func, dest_func):
    '''
    if action_cn in ["移动", "重命名", "创建", "删除"]:
        fc_handler.add_change(source_file)
        fc_handler.add_change(destination_file)
    '''
    if action_cn == "移动":
        fc_handler.add_change(src_file, _func=src_func, src_file_flag=True)
        fc_handler.add_change(dest_file, _func=dest_func)
    elif action_cn == "重命名":
        fc_handler.add_change(src_file, _func=src_func, src_file_flag=True)
        fc_handler.add_change(dest_file, _func=dest_func)
    elif action_cn == "创建":
        fc_handler.add_change(src_file, _func=dest_func)
    elif action_cn == "删除":
        fc_handler.add_change(src_file, _func=src_func, src_file_flag=True)
    else:
        # logger.error(f"未知的文件变更类型：{action_cn}！")
        pass


@index_bp.route('/file_notify', methods=['POST'])
def file_noify():
    """
    接收文件系统监听器的 webhook POST 请求
    """
    data = request.json
    if not data:
        return jsonify({"状态": "错误", "消息": "无效的 JSON 数据"}), 400

    notifications = []
    manual_scan_pathlist_func = functools.partial(
        manual_scan_dest_pathlist,
        servers_cfg=current_app.config['MEDIA_SERVERS'],
        storage_client=storage_client,
        db=redis_db,
    )
    manual_scan_deleted_pathlist_func = functools.partial(
        manual_scan_deleted_pathlist,
        servers_cfg=current_app.config['MEDIA_SERVERS'],
        storage_client=storage_client,
        db=redis_db,
    )
    for item in data.get("data", []):
        source_file = item.get("source_file", "未知路径")
        destination_file = item.get("destination_file", "无")
        src_ext = os.path.splitext(source_file)[1]
        action_cn = fc_handler.translate_action(item.get("action", "未知"), source_file, destination_file)
        is_dir_cn = "目录" if item.get("is_dir") == "true" else "文件"
        # 过滤“文件变更”
        path_not_allowed = True
        for kw in fc_handler.allowed_keywords:
            if kw in source_file or kw in destination_file:
                path_not_allowed = False
                break
        if path_not_allowed:
            continue
        elif is_dir_cn == "文件" and src_ext not in fc_handler.allowed_extensions:
            continue

        notification = {"动作": action_cn, "类型": is_dir_cn, "源路径": source_file, "目标路径": destination_file}
        notifications.append(notification)

        # 根据操作记录目录变动
        add_change2fc_handler(
            action_cn, source_file, destination_file, manual_scan_deleted_pathlist_func, manual_scan_pathlist_func
        )

    # 打印通知信息
    if len(notifications) > 0:
        logger.warning(f"收到文件变更通知： {notifications}")

    # 发送文件变更通知到其他设备
    if fc_handler.sync_other_device_enabled:
        # fc_handler.sync_filechange_to_other_device(request.url, data)
        async_filechange_to_other_device.apply_async(args=[request.url, data])
    # 响应
    return jsonify({"状态": "成功", "消息": "已接收文件系统通知"}), 200
