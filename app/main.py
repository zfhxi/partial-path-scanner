#
# 第一个参数，bool类型，是否只初始化数据库，不扫描
#
import sys
import os
from datetime import datetime
from keyvalue_sqlite import KeyValueSqlite
import functools
from termcolor import colored

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fsops import parallel_walker_mt, get_mtime, custom_get_mtime
from scanner import PlexScanner, EmbyScanner
from utils import get_pids_by_name, str2bool, read_config


def find_updated_folders(full_sub_d, db, get_mtime_func, blacklist):
    # 找出哪个子目录或者文件变更了，只遍历一级深度（不进行向下递归）
    updated_folders = []
    subs = os.listdir(full_sub_d)
    for sub in subs:
        full_sub_sub = os.path.join(full_sub_d, sub)
        if full_sub_sub in blacklist or sub.startswith("."):
            continue
        base_mtime = db.get(full_sub_sub)
        new_mtime = get_mtime_func(full_sub_sub)
        if base_mtime is None or base_mtime != new_mtime:
            updated_folders.append(full_sub_sub)
            db.set(full_sub_sub, new_mtime)
    # 当文件夹A找不到被更新的子目录B1或子文件B2（有可能删除了B3，导致了A的mtime产生了变化），添加A作为更新目录
    # 但这样做可能扫描很多内容，比如删除了`/115/电影/天空之城`这个文件夹，会导致刷新`/115/电影`整个目录
    # if len(updated_folders) == 0:
    #    updated_folders.append(full_sub_d)
    return updated_folders


def scanning_worker(path, db, only_db_initializing, get_mtime_func, scanners, overwrite_db, blacklist):
    base_mtime = db.get(path)
    new_mtime = get_mtime_func(path)
    if base_mtime is None or base_mtime != new_mtime:
        if not only_db_initializing:
            # 找出产生更新的子目录来进行扫库
            updated_folders = find_updated_folders(path, db, get_mtime_func=get_mtime_func, blacklist=blacklist)
            for uf in updated_folders:
                print(colored(f"[INFO] 目录[{uf}]有变动!", "light_green"))
                for scanner in scanners:
                    scanner.scan_directory(uf)
            db.set(path, new_mtime)
        elif base_mtime is None or overwrite_db:
            db.set(path, new_mtime)
            print(colored(f"[INFO] 目录[{path}]的mtime更新为{new_mtime}", "dark_grey"))


def launch(db, config):
    servers = config.get("servers")
    scanners = []
    if 'plex' in servers:
        scanners.append(PlexScanner(config))
    elif 'emby' in servers:
        scanners.append(EmbyScanner(config))
    else:
        pass
    monitored_folder_dict = config.get("MONITOR_FOLDER", {})
    monitored_folders = list(monitored_folder_dict.keys())
    if len(sys.argv) < 2:
        only_db_initializing = False
    else:
        only_db_initializing = str2bool(sys.argv[1])
        if only_db_initializing:
            print(f"[INFO] 只构建数据库！")

    for _folder in monitored_folders:
        _blacklist = list(map(lambda x: x.rstrip('/'), monitored_folder_dict[_folder].get("blacklist", [])))
        _splitlevel = int(monitored_folder_dict[_folder].get("split_level", 2))
        custom_mtime_flag = monitored_folder_dict[_folder].get("custom_mtime", False)
        overwrite_db_flag = monitored_folder_dict[_folder].get("overwrite_db", False)
        worker_partial = functools.partial(
            scanning_worker,
            db=db,
            only_db_initializing=only_db_initializing,
            get_mtime_func=custom_get_mtime if custom_mtime_flag else get_mtime,
            scanners=scanners,
            overwrite_db=overwrite_db_flag,
            blacklist=_blacklist,
        )
        # 监测目录自身
        worker_partial(_folder)
        # 监测子目录、子文件
        dirs_iter = parallel_walker_mt(_folder, exclude_dirs=_blacklist, level=_splitlevel)
        for _d in dirs_iter:
            worker_partial(_d)
    # pass


if __name__ == "__main__":
    if bool(get_pids_by_name("main.py")):
        # print("[ERROR] 已存在运行的监测任务！结束本次任务！")
        sys.exit(1)
    t_start = datetime.now()
    print(f"\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    print(colored(f"开始监测@{t_start.replace(microsecond=0)}...", "green"))
    CONFIG_FILE = os.getenv("CONFIG_FILE", "./config/config.yaml")
    DB_PATH = os.getenv("DB_FILE", "./config/dbkv.sqlite")
    try:
        config = read_config(CONFIG_FILE)
        db = KeyValueSqlite(DB_PATH, "mtimebasedscan4plex")
        launch(db, config)
    except Exception as e:
        print(colored("[ERROR] 监测or刷新失败！", "red"))
        print(e)
    finally:
        pass
    t_end = datetime.now()
    total_seconds = (t_end - t_start).total_seconds()
    if total_seconds < 60:
        print(colored(f"[INFO] 耗时{total_seconds:.2f} seconds!", "cyan"))
    else:
        total_minutes = total_seconds / 60
        print(colored(f"[INFO] 耗时{total_minutes:.2f} minutes!", "cyan"))
    print(colored(f"结束监测@{t_end.replace(microsecond=0)}   ", "green"))
    print(f"<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
