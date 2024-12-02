import os
from flask import render_template, request, Blueprint, jsonify, abort, current_app
from flask_login import login_required
from app.extensions import cd2, redis_db
from app.utils import getLogger, sort_list_mixedversion, timestamp_to_datetime, MtimeUpdateStrategySchema
from app.tasks import mtime_updating, mtime_clearing

logger = getLogger(__name__)

files_bp = Blueprint('files', __name__, url_prefix='/files')


@files_bp.route('/', defaults={'req_path': '/'})
@files_bp.route('/<path:req_path>/')
@login_required
def files(req_path):
    scheduler_default_interval = current_app.config['SCHEDULER_DEFAULT_INTERVAL']
    req_path = req_path if req_path.startswith('/') else f'/{req_path}'

    # Return 404 if path doesn't exist
    if not cd2.fs.exists(req_path):
        return abort(404)

    # Check if path is a file and serve
    if not cd2.fs.attr(req_path)['isDirectory']:
        # return send_file(req_path)
        pass
        return

    # Show directory contents
    files_metadata = cd2.fs.listdir_attr(req_path)
    files = []
    total_count = 0
    file_count = 0
    dir_count = 0
    sorted_names = sort_list_mixedversion([x['name'] for x in files_metadata])
    sort_name_map = {}
    _adjuster = len(str(len(sorted_names)))
    for i, name in enumerate(sorted_names):
        sort_name_map[name] = str(i + 1).zfill(_adjuster)
    for file_meta in files_metadata:
        path = file_meta['path']
        isdir = file_meta['isDirectory'] if req_path != '/' else True
        mtime = cd2.fs.attr(path)['mtime']
        dbmtime = redis_db.get(path)
        if not isdir or not dbmtime or float(dbmtime) < mtime:
            need_update = True
        else:
            need_update = False
        files.append(
            {
                "name": file_meta['name'],
                "path": path,
                "isdir": isdir,
                "mtime": timestamp_to_datetime(mtime),
                "dbtime": timestamp_to_datetime(dbmtime) if dbmtime else '-',
                "need_update": need_update,
                "link": f"/files/{os.path.join( req_path, file_meta['name'])}",
                "sort_index": sort_name_map[file_meta['name']],
            }
        )
        if isdir:
            dir_count += 1
        else:
            file_count += 1
        total_count += 1
    path_units = list(filter(lambda x: x != '', req_path.split(os.path.sep)))
    path_unit_links = [("主页", "/files")]
    for unit in path_units:
        path_unit_links.append((unit, os.path.join(path_unit_links[-1][1], unit)))

    return render_template(
        '/files/files.html',
        path_unit_links=path_unit_links,
        req_path=req_path,
        files=files,
        counts=(dir_count, file_count, total_count),
        scheduler_default_interval=scheduler_default_interval,
    )


def mtime_updating_task_wrapper(mtime_update_strategy, folder, blacklist):
    servers_cfg = current_app.config['MEDIA_SERVERS']
    if mtime_update_strategy == 'partial':
        task = mtime_updating.delay(
            folder,
            blacklist,
            servers_cfg,
            fetch_mtime_only=True,
            fetch_all_mode=False,
        )
        message = f"后台增量更新目录[{folder}]及其子目录缺失的mtime..."
    elif mtime_update_strategy == 'full':
        task = mtime_updating.delay(
            folder,
            blacklist,
            servers_cfg,
            fetch_mtime_only=True,
            fetch_all_mode=True,
        )
        message = f"后台全量更新目录[{folder}]及其子目录的mtime..."
    elif mtime_update_strategy == 'reset':
        task = mtime_clearing.delay(folder)
        message = f"后台清空目录[{folder}]及其子目录的mtime..."
    else:
        task = None
        message = ""
    return task, message


@files_bp.route('/update_mtime/', methods=['PUT'])
@login_required
def monitored_folder_edit():
    schema = MtimeUpdateStrategySchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify(status='error', message=str(e))
    folder = data['folder']
    mtime_update_strategy = data.get('mtime_update_strategy', 'disabled')
    try:
        # 根据条件来更新mtime
        task, _msg = mtime_updating_task_wrapper(mtime_update_strategy, folder, blacklist=[])
        message = _msg
        if task:
            logger.info(f"{message}, 任务ID：{task.id}")
        else:
            logger.info(message)
        rval = True
    except Exception as e:
        message = f"更新目录[{folder}]的mtime失败！{e}"
        logger.error(message)
        rval = False

    return jsonify(status='success' if rval else 'error', message=message)
