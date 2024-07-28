import sys
import os
import functools
from datetime import datetime

from keyvalue_sqlite import KeyValueSqlite
from clouddrive import CloudDriveClient, CloudDrivePath

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scanner import PlexScanner, EmbyScanner, ScanType
from utils import getLogger, get_other_pids_by_script_name, load_yaml_config, str2bool

logger = getLogger(__name__)


def get_mtime(path, fs):
    try:
        # if os.path.exists(path):
        if isinstance(path, CloudDrivePath):
            mtime = path.mtime
        elif isinstance(path, str):
            mtime = fs.attr(path)['mtime']
        else:
            raise TypeError(f"Invalid path type: {type(path)}")
        # return f"{mtime}|{time.ctime(mtime)}
        return f"{mtime}"
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


def find_updated_folders(top, fs, db, blacklist):
    # 找出哪个子目录或者文件变更了，只遍历一级深度（不进行向下递归）
    updated_folders = []
    subs = fs.listdir_attr(top)
    # subs = fs.listdir_path(full_sub_d)
    for sub in subs:
        sub_full_path = sub['path']
        if sub_full_path in blacklist or sub['name'].startswith("."):
            continue
        base_mtime = db.get(sub_full_path)
        new_mtime = sub['mtime']
        if base_mtime is None or base_mtime != new_mtime:
            updated_folders.append(sub_full_path)
            db.set(sub_full_path, new_mtime)
    # 当文件夹A找不到被更新的子目录B1或子文件B2（有可能删除了B3，导致了A的mtime产生了变化），添加A作为更新目录
    # 但这样做可能扫描很多内容，比如删除了`/115/电影/天空之城`这个文件夹，会导致刷新`/115/电影`整个目录
    # if len(updated_folders) == 0:
    #    updated_folders.append(full_sub_d)
    return updated_folders


def path_scan_workder(
    path,
    db,
    only_db_initializing,
    overwrite_db,
    get_mtime_func,
    find_updated_folders_func,
    scanning_func,
):
    base_mtime = db.get(path)
    new_mtime = get_mtime_func(path)
    if base_mtime is None or base_mtime != new_mtime:
        if not only_db_initializing:
            # 找出产生更新的子目录来进行扫库
            updated_folders = find_updated_folders_func(path)
            scanning_func(updated_folders)
            db.set(path, new_mtime)
        elif base_mtime is None or overwrite_db:
            db.set(path, new_mtime)
            logger.info(f"Mtime of path[{path}] has been updated to {new_mtime}.")


def fs_walk(fs, top: str, blacklist=[], **kwargs):
    for path, dirs, files in fs.walk_attr(top, topdown=True, **kwargs):
        _dirs = [d for d in dirs if d['path'] not in blacklist]  # not valid when topdown=False
        dirs[:] = _dirs
        yield path, [a["name"] for a in dirs], [a["name"] for a in files]


def scanning_process(path_list, fs, scanners):
    file_queue = []
    path_queue = []
    for path in path_list:
        file_queue.append(path)
        if fs.attr(path)['isDirectory']:
            path_queue.append(path)
        else:
            path_queue.append(os.path.dirname(path))
    file_queue = set(file_queue)
    path_queue = set(path_queue)
    for scanner in scanners:
        if scanner.scan_type == ScanType.FILE_BASED:
            queue = file_queue
        elif scanner.scan_type == ScanType.PATH_BASED:
            queue = path_queue
        else:
            raise ValueError(f"Invalid scan type: {scanner.scan_type}")
        for path in queue:
            scanner.scan_directory(path)


def launch(config):
    cd2_client = CloudDriveClient(config['cd2']['host'], config['cd2']['user'], config['cd2']['password'])
    fs = cd2_client.fs
    DB_PATH = os.getenv("DB_FILE", "./config/dbkv.sqlite")
    db = KeyValueSqlite(DB_PATH, "mtimebasedscan")

    servers = config.get("servers")
    monitored_folder_dict = config.get("MONITOR_FOLDER", {})
    monitored_folders = list(monitored_folder_dict.keys())
    get_mtime_func = functools.partial(get_mtime, fs=fs)
    scanners = []
    if 'plex' in servers:
        scanners.append(PlexScanner(config))
    if 'emby' in servers:
        scanners.append(EmbyScanner(config))
    scanning_func = functools.partial(scanning_process, fs=fs, scanners=scanners)

    if len(sys.argv) < 2:
        only_db_initializing = False
    else:
        only_db_initializing = str2bool(sys.argv[1])
        if only_db_initializing:
            logger.info(f"Build the database for the first time only!")

    for _folder in monitored_folders:
        _blacklist = list(map(lambda x: x.rstrip('/'), monitored_folder_dict[_folder].get("blacklist", [])))
        overwrite_db_flag = monitored_folder_dict[_folder].get("overwrite_db", False)
        find_updated_folders_func = functools.partial(find_updated_folders, fs=fs, db=db, blacklist=_blacklist)
        worker_partial = functools.partial(
            path_scan_workder,
            db=db,
            only_db_initializing=only_db_initializing,
            overwrite_db=overwrite_db_flag,
            get_mtime_func=get_mtime_func,
            find_updated_folders_func=find_updated_folders_func,
            scanning_func=scanning_func,
        )
        # 监测子目录、子文件
        for root, dirs, files in fs_walk(fs, top=_folder, blacklist=_blacklist):
            worker_partial(root)


if __name__ == "__main__":
    if bool(get_other_pids_by_script_name("main.py")):
        logger.warning("A monitoring task is already running!")
        # sys.exit(1)
    t_start = datetime.now()
    logger.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")  # fmt: skip
    logger.info(f"Start to monitoring folders@{t_start.replace(microsecond=0)}...")
    CONFIG_FILE = os.getenv("CONFIG_FILE", "./config/config.yaml")
    try:
        config = load_yaml_config(CONFIG_FILE)
        launch(config)
    except Exception as e:
        logger.error(f"Failed to monitor or refresh folders！")
        logger.error(e)
    finally:
        pass
    t_end = datetime.now()
    total_seconds = (t_end - t_start).total_seconds()
    if total_seconds < 60:
        logger.info(f"Time cost: {total_seconds:.2f} seconds!")
    else:
        total_minutes = total_seconds / 60
        logger.info(f"Time cost: {total_minutes:.2f} minutes!")
    logger.warning(f"End of monitoring folders@{t_end.replace(microsecond=0)}!")
    logger.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")  # fmt: skip
