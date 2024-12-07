from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required
from app.database import MonitoredFolder
from app.extensions import sqlite_db, scheduler, redis_db, storage_client

from app.tasks import mtime_updating, manual_scan_bg
from app.utils import (
    MonitoredFolderDataSchema,
    EditMonitoredFolderDataSchema,
    EditMonitoredFolderStatusSchema,
    FolderBaseSchema,
    getLogger,
    create_folder_scheduler,
    manual_scan,
    sort_list_by_pinyin,
    str2bool,
)

monitor_bp = Blueprint('index', __name__, url_prefix='/monitor')
logger = getLogger(__name__)

# you can ignore this function as you're doing request on same origin
"""
@app.after_request
def allow_cors_origin(response):
    # Resolve CORS error
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,PATCH,OPTIONS")
    return response
"""


@monitor_bp.route('/', methods=['GET', 'POST'])
# @monitor_bp.route('/index/', methods=['GET', 'POST'])
@login_required
def index():
    scheduler_default_interval = current_app.config['SCHEDULER_DEFAULT_INTERVAL']
    return render_template('/monitor/index.html', scheduler_default_interval=scheduler_default_interval)


def mtime_updating_when_update_folder_task_wrapper(mtime_update_strategy, folder, blacklist):
    servers_cfg = current_app.config['MEDIA_SERVERS']
    if mtime_update_strategy == 'partial':
        task = mtime_updating.apply_async(args=[folder, blacklist, servers_cfg, True, False])
        message = f"后台更新缺失的目录mtime..."
    elif mtime_update_strategy == 'full':
        task = mtime_updating.apply_async(args=[folder, blacklist, servers_cfg, True, True])
        message = f"后台全量更新目录mtime..."
    else:
        task = None
        message = ""
    if task:
        logger.info(f"{message}, 任务ID：{task.id}")
    return task, message


@monitor_bp.route('/add/', methods=['POST'])
@login_required
def monitored_folder_add():
    schema = MonitoredFolderDataSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify(status='error', message=str(e))

    folder = data['folder']
    interval = data.get('interval', '1 day')
    offset = float(data.get('offset', '-1'))
    blacklist = data.get('blacklist', [])
    # overwrite_db = data.get('overwrite_db', 'False')
    enabled = str2bool(data.get('enabled', 'True'))
    mtime_update_strategy = data.get('mtime_update_strategy', 'disabled')
    rval = True
    result = MonitoredFolder.query.get(folder)
    if result:
        message = f"监控目录[{folder}]已存在！"
        logger.error(message)
        rval = False
    else:
        monitored_folder = MonitoredFolder(
            folder=folder,
            enabled=enabled,
            blacklist=blacklist,
            interval=interval,
            offset=offset,
        )
        sqlite_db.session.add(monitored_folder)
        sqlite_db.session.commit()

        # 创建定时任务
        create_folder_scheduler(
            monitored_folder=monitored_folder,
            servers_cfg=current_app.config['MEDIA_SERVERS'],
            scheduler=scheduler,
            storage_client=storage_client,
            db=redis_db,
        )
        message = f"监控目录[{folder}]已添加！"
        # 根据条件来更新mtime
        _, _msg = mtime_updating_when_update_folder_task_wrapper(mtime_update_strategy, folder, blacklist)
        message += _msg
        logger.info(message)
        rval = True
    return jsonify(status='success' if rval else 'error', message=message)


@monitor_bp.route('/edit/', methods=['PUT'])
@login_required
def monitored_folder_edit():
    schema = EditMonitoredFolderDataSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify(status='error', message=str(e))
    new_folder = data['new_folder']
    folder = data['folder']
    interval = data['interval']
    offset = data['offset']
    blacklist = data['blacklist']
    enabled = data['enabled']
    try:
        if new_folder == folder:  # 未修改监控目录名
            MonitoredFolder.query.filter(MonitoredFolder.folder == folder).update(
                {
                    "enabled": enabled,
                    "blacklist": blacklist,
                    "interval": interval,
                    "offset": offset,
                }
            )
            sqlite_db.session.commit()
            if scheduler.get_job(folder):
                scheduler.remove_job(folder)

            message = f"监控目录[{folder}]已修改！"

        else:  # 修改了监控目录名
            result = MonitoredFolder.query.get(new_folder)
            if result:
                return jsonify(status='error', message=f"监控目录[{new_folder}]已存在！终止修改。")
            MonitoredFolder.query.filter(MonitoredFolder.folder == folder).delete()
            monitor_folder = MonitoredFolder(
                folder=new_folder,
                enabled=enabled,
                blacklist=blacklist,
                interval=interval,
                offset=offset,
            )
            sqlite_db.session.add(monitor_folder)
            sqlite_db.session.commit()
            if scheduler.get_job(folder):
                scheduler.remove_job(folder)
            message = f"监控目录[{folder}]->[{new_folder}]已修改！"
        # 重新创建定时任务
        monitored_folder = MonitoredFolder.query.get(new_folder)
        create_folder_scheduler(
            monitored_folder=monitored_folder,
            servers_cfg=current_app.config['MEDIA_SERVERS'],
            scheduler=scheduler,
            storage_client=storage_client,
            db=redis_db,
        )
        logger.info(message)
        rval = True
    except Exception as e:
        message = f"修改监控目录[{folder}]失败！{e}"
        logger.error(message)
        rval = False

    return jsonify(status='success' if rval else 'error', message=message)


@monitor_bp.route('/edit_status/', methods=['PUT'])
@login_required
def monitered_folder_edit_status():
    schema = EditMonitoredFolderStatusSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify(status='error', message=str(e))
    folder = data['folder']
    new_enabled = data['enabled']
    try:
        MonitoredFolder.query.filter(MonitoredFolder.folder == folder).update({"enabled": new_enabled})
        sqlite_db.session.commit()
        monitored_folder = MonitoredFolder.query.get(folder)
        if not new_enabled:
            if scheduler.get_job(folder):
                scheduler.remove_job(folder)
        else:
            if scheduler.get_job(folder) is None:
                create_folder_scheduler(
                    monitored_folder=monitored_folder,
                    servers_cfg=current_app.config['MEDIA_SERVERS'],
                    scheduler=scheduler,
                    storage_client=storage_client,
                    db=redis_db,
                )
        message = f"监控目录[{folder}]已{'启用' if new_enabled else '禁用'}！"
        rval = True
        logger.info(message)
    except Exception as e:
        message = f"监控目录[{folder}]状态更改失败！{e}"
        logger.error(message)
        rval = False

    return jsonify(status='success' if rval else 'error', message=message)


@monitor_bp.route('/delete/', methods=['DELETE'])
@login_required
def monitored_folder_delete():
    schema = FolderBaseSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify(status='error', message=str(e))
    folder = data['folder']
    MonitoredFolder.query.filter(MonitoredFolder.folder == folder).delete()
    sqlite_db.session.commit()
    # 移除该目录的定时任务
    if scheduler.get_job(folder):
        scheduler.remove_job(folder)
    message = f"监控目录[{folder}]已删除！"
    logger.warning(message)
    return jsonify(status='success', message=message)


@monitor_bp.route('/list/', methods=['GET'])
@login_required
def monitored_folder_list():
    results = MonitoredFolder.query.all()
    folders = []
    for res in results:
        pass
        job = scheduler.get_job(res.folder)
        if job:
            # next_run_time = (job.next_run_time).strftime("%Y-%m-%d %H:%M:%S")
            next_run_time = (job.next_run_time).strftime("%m-%d %H:%M:%S")
        else:
            next_run_time = "-"
        folders.append(
            {
                'name': res.folder,
                "enabled": res.enabled,
                'blacklist': ','.join(res.blacklist),
                'interval': res.interval,
                'offset': res.offset,
                'next_run_time': next_run_time,
                # 'sort_index': sorted_name_map[k],
            }
        )
    _folder_names = [f['name'] for f in folders]
    sorted_folder_names = sort_list_by_pinyin(_folder_names)
    sorted_name_map = {}
    # print(folders)
    _adjuster = len(str(len(sorted_folder_names)))
    for i, name in enumerate(sorted_folder_names):
        sorted_name_map[name] = str(i + 1).zfill(_adjuster)
    for i in range(len(folders)):
        folders[i]['sort_index'] = sorted_name_map[_folder_names[i]]

    return jsonify(folders)


@monitor_bp.route('/scan/', methods=['POST'])
@login_required
def monitored_folder_scan():
    schema = FolderBaseSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify(status='error', message=str(e))
    folder = data['folder']
    job = scheduler.get_job(folder)
    if job:
        # 是否需要判断job是否暂停？
        job.modify(next_run_time=datetime.now())
        message = f"已触发目录[{folder}]的遍历！"
        logger.info(message)
        return jsonify(status='success', message=message)
    else:
        message = f"目录[{folder}]的监控未启用！"
        logger.error(message)
        return jsonify(status='error', message=message)


@monitor_bp.route('/scan_folder_unconditionally/', methods=['POST'])
@login_required
def scan_folder_unconditionally():
    schema = FolderBaseSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify(status='error', message=str(e))
    folder = data['folder']
    # rval, message = manual_scan(folder, current_app.config['MEDIA_SERVERS'], cd2, redis_db)
    try:
        task = manual_scan_bg.apply_async(args=[folder, current_app.config['MEDIA_SERVERS']])
        if task:
            message = f"已提交手动扫描路径[{folder}]的后台任务！, 任务ID：{task.id}"
        else:
            raise Exception(f"创建手动扫描路径[{folder}]后台任务失败！{e}")
        logger.info(message)
        rval = True
    except Exception as e:
        message = e
        rval = False
    return jsonify(status='success' if rval else 'error', message=message)
