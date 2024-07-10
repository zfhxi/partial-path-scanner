import os
import yaml
import time
from datetime import datetime
from plexapi.server import PlexServer
from pathlib import Path
from urllib.parse import quote_plus
from keyvalue_sqlite import KeyValueSqlite
import functools


def str2bool(v):
    if isinstance(v, bool):
        return v
    elif v in ["True", "true", "1"]:
        return True
    elif v in ["False", "true", "0"]:
        return False
    else:
        raise ValueError("Boolean value expected.")


def read_config(yaml_fn):
    with open(yaml_fn, "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def get_mtime(path, listdir=False):
    mtime = os.path.getmtime(path)
    if listdir:
        folder_len = len(os.listdir(path))
        return f"{mtime}|{time.ctime(mtime)}|{folder_len}"
    else:
        return f"{mtime}|{time.ctime(mtime)}"


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
        print(f"查找媒体库出错：{str(err)}")
    return "", ""


def plex_scan_specific_path(pms, plex_libraies, directory):
    lib_key, path = plex_find_libraries(Path(directory), plex_libraies)
    print(f"刷新媒体库：{lib_key} - {path}")
    pms.query(f"/library/sections/{lib_key}/refresh?path={quote_plus(str(Path(path).parent))}")


def monitoring_and_scanning(db, config, pms):
    monitored_folder_dict = config.get("MONITOR_FOLDER", {})

    monitored_folders = list(monitored_folder_dict.keys())
    plex_libraies = pms.library.sections()

    for _folder in monitored_folders:
        _blacklist = set(monitored_folder_dict[_folder].get("blacklist", []))
        listdir_flag = str2bool(monitored_folder_dict[_folder].get("listdir", False))
        get_mtime_bylistdir = functools.partial(get_mtime, listdir=listdir_flag)
        # 监测目录自身
        base_mtime = db.get(_folder)
        new_mtime = get_mtime_bylistdir(_folder)
        if base_mtime is None or base_mtime != new_mtime:
            plex_scan_specific_path(pms, plex_libraies, Path(_folder))
            db.set(_folder, new_mtime)
            print(f"Update mtime to {new_mtime} for {_folder}.")
        # 监测子目录、子文件
        for root, dirs, files in os.walk(_folder, topdown=True):
            _dirs = []
            for sub_d in dirs:
                if sub_d.startswith(".") or os.path.join(root, sub_d) in _blacklist:
                    # 排除黑名单里的目录，和以.开头的隐藏目录
                    continue
                full_sub_d = os.path.join(root, sub_d)
                base_mtime = db.get(full_sub_d)
                new_mtime = get_mtime_bylistdir(full_sub_d)
                if base_mtime is None or base_mtime != new_mtime:
                    plex_scan_specific_path(pms, plex_libraies, Path(full_sub_d))
                    db.set(full_sub_d, new_mtime)
                    print(f"Update mtime to {new_mtime} for {full_sub_d}.")
                    _dirs.append(sub_d)
            # 跳过那些不满足条件的子目录的深度遍历
            # 将dirs通过in-place方式修改，即后面只遍历dirs中的目录以及子目录、文件
            # 参考https://stackoverflow.com/questions/51954665/exclude-specific-folders-and-subfolders-in-os-walk
            dirs = _dirs
    return 0


if __name__ == "__main__":
    print(f"\n###############################")
    print(f"开始检测@{datetime.now().replace(microsecond=0)}...")
    print(f"###############################")
    CONFIG_FILE = os.getenv("CONFIG_FILE", "./config/config.yaml")
    DB_PATH = os.getenv("DB_FILE", "./config/dbkv.sqlite")

    try:
        config = read_config(CONFIG_FILE)
        db = KeyValueSqlite(DB_PATH, "mtimebasedscan4plex")
        pms = PlexServer(config["plex"]["host"], config["plex"]["token"])
        monitoring_and_scanning(db, config, pms)
    except Exception as e:
        print("检测or刷新失败！")
        print(e)

## 感谢https://github.com/jxxghp/MoviePilot/blob/19165eff759f14e9947e772c574f9775b388df0e/app/modules/plex/plex.py#L355
