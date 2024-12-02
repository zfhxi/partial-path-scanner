import os, sys, time
from pathlib import Path
from plexapi.server import PlexServer
from urllib.parse import quote_plus
import requests
from requests import RequestException

# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# from utils import getLogger
from app.utils import getLogger


logger = getLogger(__name__)


def is_subpath(_path: Path, _parent: Path) -> bool:
    """
    Determine if _path is a subdirectory of _parent.
    """
    _path = _path.resolve()
    _parent = _parent.resolve()
    return _path.parts[: len(_parent.parts)] == _parent.parts


def get_path_mapping_rules(server_config):
    path_mapping = server_config.get("path_mapping", {})
    path_mapping_enable = path_mapping.get('enabled', False)
    if path_mapping_enable:
        rule_set = []
        path_mapping_rules = path_mapping.get('rules', [])
        for rule in path_mapping_rules:
            rule_set.append((rule.get('from', ''), rule.get('to', '')))
        return rule_set
    else:
        return []


# refer to:
# https://github.com/jxxghp/MoviePilot/blob/19165eff759f14e9947e772c574f9775b388df0e/app/modules/plex/plex.py#L355
class PlexScanner:
    def __init__(self, config) -> None:
        self.server_type = 'plex'
        # self.server_cnf = config[self.server_type]
        self.server_cnf = config
        try:
            self.pms = PlexServer(self.server_cnf["host"], self.server_cnf["token"])
            self._libraies = self.pms.library.sections()
        except Exception as e:
            logger.error(f"[PLEX] Failed to connect to the Plex Media Server!\n{e}")
        self.path_mapping_rules = get_path_mapping_rules(self.server_cnf)
        self.isfile_based_scanning = self.server_cnf.get('isfile_based_scanning', True)

    def reconnect(self):
        try:
            self.pms = PlexServer(self.server_cnf["host"], self.server_cnf["token"])
            self._libraies = self.pms.library.sections()
        except Exception as e:
            logger.error(f"[PLEX] Failed to connect to the Plex Media Server!\n{e}")

    def find_library_by_path(self, path: Path) -> str:
        """
        Determine which media this path belongs to.
        """

        if path is None:
            return ""
        try:
            for lib in self._libraies:
                if hasattr(lib, "locations") and lib.locations:
                    for location in lib.locations:
                        if is_subpath(path, Path(location)):
                            if path.is_file():
                                # plex media server only supports refreshing folders not files
                                # path = path.parent
                                pass
                            # return lib.key, lib.title, str(path)
                            return lib.key
        except Exception as err:
            logger.error(f"[PLEX] Unable to find a library for the path[{path.as_posix()}]\n{err}")
        return ""

    # def plex_scan_specific_path(self, plex_libraies, directory):
    def scan_path(self, path: str, **kwargs) -> bool:
        for rule in self.path_mapping_rules:
            if path.startswith(rule[0]):
                path = path.replace(rule[0], rule[1], 1)
                break
        try:
            lib_key = self.find_library_by_path(Path(path))
            if not bool(lib_key):
                logger.error(f"路径[{path}]未被包含在何媒体库的子目录中!")
                return False
            if bool(lib_key) and bool(path):
                # logger.info(f"[PLEX] Scanning the library[{lib_title}] - path[{path}]")
                self.pms.query(f"/library/sections/{lib_key}/refresh?path={quote_plus(Path(path).as_posix())}")
                time.sleep(1)
                return True
            else:
                logger.error(f"[PLEX] Unable to find a library for the path[{path}]!")
                return False
        except Exception as e:
            logger.error(f"[PLEX] Failed to scan the path[{path}]!\n{e}")
            return False


# refer to:
# https://github.com/NiNiyas/autoscan/blob/master/jelly_emby.py#L88
# https://github.com/jxxghp/MoviePilot/blob/19165eff759f14e9947e772c574f9775b388df0e/app/modules/emby/emby.py
class EmbyScanner:
    def __init__(self, config) -> None:
        self.server_type = 'emby'
        # self.server_cnf = config[self.server_type]
        self.server_cnf = config
        self.host = self.server_cnf['host']
        self.api_key = self.server_cnf['api_key']
        self.path_mapping_rules = get_path_mapping_rules(self.server_cnf)
        self.isfile_based_scanning = self.server_cnf.get('isfile_based_scanning', True)
        # 获取所有媒体文件夹
        self.library_folders_map = {}
        self.folders_library_map = {}
        self.library_all_folders = []
        self.get_libraries()

    def get_libraries(self):
        try:
            response = requests.get(
                self.host + f'/Library/SelectableMediaFolders?api_key={self.api_key}',
            )
            data = response.json()
            # self.folders = response.json()
            for library_meta in data:
                library_name = library_meta['Name']
                raw_sub_folders = library_meta['SubFolders']
                sub_folders = []
                for _sub in raw_sub_folders:
                    sub_folders.append(_sub['Path'])
                    self.folders_library_map[_sub['Path']] = library_name

                self.library_folders_map[library_name] = sub_folders
                self.library_all_folders.extend(sub_folders)
        except RequestException as e:
            logger.error(f"Failed to get libraries from {self.server_type}!\n{e}")

    def find_library_by_path(self, path: Path) -> str:
        if path is None:
            return ""
        for lib_sub_path in self.library_all_folders:
            if is_subpath(path, Path(lib_sub_path)):
                return self.folders_library_map[lib_sub_path]
        return ""

    def scan_path(self, path: str, **kwargs) -> bool:
        for rule in self.path_mapping_rules:
            if path.startswith(rule[0]):
                path = path.replace(rule[0], rule[1], 1)
                break
        data = {"Updates": [{"Path": f"{path}", "UpdateType": "Created"}]}
        headers = {"accept": "application/json", "Content-Type": "application/json"}
        try:
            lib_name = self.find_library_by_path(Path(path))
            if not bool(lib_name):
                logger.error(f"路径[{path}]未被包含在何媒体库的子目录中!")
                return False
            command = requests.post(
                self.host + f'/Library/Media/Updated?api_key={self.api_key}',
                headers=headers,
                json=data,
            )
            time.sleep(1)
            if command.status_code == 204:
                # logger.info(f"[{self.server_type.upper()}] Scanning the path[{directory}]")
                pass
                return True
            else:
                logger.error(f"Failed to scan the path[{path}]!")
                return False
        except RequestException as e:
            logger.error(f"Failed to refresh the path[{path}]!\n{e}")
            # raise RequestException(f"Error occurred when trying to send scan request to {self.server_type}. {e}")
            return False
