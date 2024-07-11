#
# 第一个参数，bool类型，是否只初始化数据库，不扫描
#
import sys
import os
import yaml
import time
from datetime import datetime
from plexapi.server import PlexServer
from pathlib import Path
from urllib.parse import quote_plus
from keyvalue_sqlite import KeyValueSqlite
import functools
import psutil
import multiprocessing


def str2bool(v):
    if isinstance(v, bool):
        return v
    elif v in ["True", "true", "1"]:
        return True
    elif v in ["False", "false", "0"]:
        return False
    else:
        raise ValueError("Boolean value expected.")


def read_config(yaml_fn):
    with open(yaml_fn, "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def get_mtime(path):
    try:
        if os.path.exists(path):
            mtime = os.path.getmtime(path)
            # return f"{mtime}|{time.ctime(mtime)}
            return f"{mtime}"
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


def my_list_folders(path):
    if os.path.isfile(path):
        # raise ValueError(f"{path} is a file!")
        return []
    else:
        folders = [entry.path for entry in os.scandir(path) if entry.is_dir()]
        return folders


def my_list_files(path):
    if os.path.isfile(path):
        return []
    else:
        files = [entry.path for entry in os.scandir(path) if entry.is_file()]
        return files


def custom_get_mtime(path):
    """
    对于/A/B/C目录
    先更新A目录的mtime为文件B1、B2、B3中最新的mtime
    """
    try:
        if os.path.exists(path):
            mtimes = [os.path.getmtime(x) for x in my_list_files(path)]
            mtime = max(mtimes) if bool(mtimes) else os.path.getmtime(path)
            return f"{mtime}"
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


def plex_find_libraries(path: Path, libraries):
    """
    判断这个path属于哪个媒体库
    多个媒体库配置的目录不应有重复和嵌套,
    """

    def is_subpath(_path: Path, _parent: Path) -> bool:
        """
        判断_path是否是_parent的子目录下
        """
        _path = _path.resolve()
        _parent = _parent.resolve()
        return _path.parts[: len(_parent.parts)] == _parent.parts

    if path is None:
        return "", ""
    try:
        for lib in libraries:
            if hasattr(lib, "locations") and lib.locations:
                for location in lib.locations:
                    if is_subpath(path, Path(location)):
                        return lib.key, str(path)
    except Exception as err:
        print(f"[ERROR] 查找媒体库出错：{str(err)}")
    return "", ""


def plex_scan_specific_path(pms, plex_libraies, directory):
    lib_key, path = plex_find_libraries(Path(directory), plex_libraies)
    if bool(lib_key) and bool(path):
        print(f"[INFO] 刷新媒体库：lib_key[{lib_key}] - path[{path}]")
        pms.query(f"/library/sections/{lib_key}/refresh?path={quote_plus(str(Path(path).parent))}")
    else:
        print(f"[ERROR] 未定位到媒体库：lib_key[{lib_key}] - path[{path}]")


def find_updated_folders(full_sub_d, db, get_mtime_func):
    # 找出哪个子目录或者文件变更了，只遍历一级深度（不进行向下递归）
    updated_folders = []
    subs = os.listdir(full_sub_d)
    for sub in subs:
        full_sub_sub = os.path.join(full_sub_d, sub)
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


def get_other_pids_by_script_name(script_name):
    pids = []
    mypid = os.getpid()
    for process in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd_line = process.info['cmdline']
            cmd_str = ' '.join(cmd_line) if cmd_line else ''
            pid = process.info['pid']
            if script_name in cmd_str and pid != mypid:
                pids.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return pids


def custom_only_scan_dir(path, exclude_dirs=[]):
    if path in exclude_dirs:
        return
    if os.path.split(path)[1].startswith('.'):
        return
    for entry in os.scandir(path):
        if entry.is_dir():
            if entry.path in exclude_dirs or entry.name.startswith('.'):
                continue
            # if any(entry.path.startswith(os.path.join(dir_path, '')) for dir_path in exclude_dirs):
            #     return
            # if os.path.split(entry.path)[1].startswith('.'):
            #     return
            yield entry.path
            yield from custom_only_scan_dir(entry.path, exclude_dirs)


def path_scan_workder(path, db, only_db_initializing, get_mtime_func, pms, plex_libraies, overwrite_db):
    base_mtime = db.get(path)
    new_mtime = get_mtime_func(path)
    if base_mtime is None or base_mtime != new_mtime:
        if not only_db_initializing:
            # 找出产生更新的子目录来进行扫库
            updated_folders = find_updated_folders(path, db, get_mtime_func=get_mtime_func)
            for uf in updated_folders:
                print(f"[INFO] 目录[{uf}]有变动!")
                plex_scan_specific_path(pms, plex_libraies, Path(uf))
            db.set(path, new_mtime)
            # print(f"Update mtime to {new_mtime} for {full_subpath}")
        elif base_mtime is None or overwrite_db:
            db.set(path, new_mtime)
            print(f"[INFO] 目录[{path}]的mtime更新为{new_mtime}")


def monitoring_and_scanning(db, config, pms):
    POOL_SIZE = int(os.getenv("POOL_SIZE", 1))
    monitored_folder_dict = config.get("MONITOR_FOLDER", {})
    monitored_folders = list(monitored_folder_dict.keys())
    plex_libraies = pms.library.sections()
    if len(sys.argv) < 2:
        only_db_initializing = False
    else:
        only_db_initializing = str2bool(sys.argv[1])
        if only_db_initializing:
            print(f"[INFO] 只构建数据库！")

    for _folder in monitored_folders:
        _blacklist = list(map(lambda x: x.rstrip('/'), monitored_folder_dict[_folder].get("blacklist", [])))
        custom_mtime_flag = monitored_folder_dict[_folder].get("custom_mtime", False)
        overwrite_db_flag = monitored_folder_dict[_folder].get("overwrite_db", False)
        worker_partial = functools.partial(
            path_scan_workder,
            db=db,
            only_db_initializing=only_db_initializing,
            get_mtime_func=custom_get_mtime if custom_mtime_flag else get_mtime,
            pms=pms,
            plex_libraies=plex_libraies,
            overwrite_db=overwrite_db_flag,
        )
        # 监测目录自身
        worker_partial(_folder)
        # 监测子目录、子文件
        if POOL_SIZE > 1:
            print(f"[INFO] 启用多进程监测，进程数：{POOL_SIZE}")
            with multiprocessing.Pool(POOL_SIZE) as p:
                p.map(worker_partial, custom_only_scan_dir(_folder, exclude_dirs=_blacklist))
        else:
            for _d in custom_only_scan_dir(_folder, exclude_dirs=_blacklist):
                worker_partial(_d)
    print(f"[INFO] 本次监测完成！")


if __name__ == "__main__":
    if bool(get_other_pids_by_script_name("main.py")):
        # print("[ERROR] 已存在运行的监测任务！结束本次任务！")
        if str2bool(os.getenv("RELEASE", True)):
            sys.exit(1)
    print(f"\n###############################")
    print(f"开始监测@{datetime.now().replace(microsecond=0)}...")
    print(f"###############################")
    CONFIG_FILE = os.getenv("CONFIG_FILE", "./config/config.yaml")
    DB_PATH = os.getenv("DB_FILE", "./config/dbkv.sqlite")

    if str2bool(os.getenv("RELEASE", True)):
        try:
            config = read_config(CONFIG_FILE)
            db = KeyValueSqlite(DB_PATH, "mtimebasedscan4plex")
            pms = PlexServer(config["plex"]["host"], config["plex"]["token"])
            monitoring_and_scanning(db, config, pms)
        except Exception as e:
            print("[ERROR] 监测or刷新失败！")
            print(e)
        finally:
            pass
    else:
        config = read_config(CONFIG_FILE)
        db = KeyValueSqlite(DB_PATH, "mtimebasedscan4plex")
        pms = PlexServer(config["plex"]["host"], config["plex"]["token"])
        i = 1
        while True:
            print(f"第{i}次监测...")
            monitoring_and_scanning(db, config, pms)
            time.sleep(2)
            i += 1

## 感谢https://github.com/jxxghp/MoviePilot/blob/19165eff759f14e9947e772c574f9775b388df0e/app/modules/plex/plex.py#L355
