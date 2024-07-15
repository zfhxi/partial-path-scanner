from pathlib import Path
from plexapi.server import PlexServer
from urllib.parse import quote_plus
import requests
from datetime import datetime
from requests import RequestException
from termcolor import colored


def current_time():
    return datetime.now().replace(microsecond=0)


def is_subpath(_path: Path, _parent: Path) -> bool:
    """
    判断_path是否是_parent的子目录下
    """
    _path = _path.resolve()
    _parent = _parent.resolve()
    return _path.parts[: len(_parent.parts)] == _parent.parts


def get_path_mapping_rules(server_config):
    path_mapping = server_config.get("path_mapping", {})
    path_mapping_enable = path_mapping.get('enable', False)
    if path_mapping_enable:
        rule_set = []
        path_mapping_rules = path_mapping.get('rules', [])
        for rule in path_mapping_rules:
            rule_set.append((rule.get('from', ''), rule.get('to', '')))
        return rule_set
    else:
        return []


# 感谢https://github.com/jxxghp/MoviePilot/blob/19165eff759f14e9947e772c574f9775b388df0e/app/modules/plex/plex.py#L355
class PlexScanner:
    def __init__(self, config) -> None:
        self.server_cnf = config["plex"]
        try:
            self.pms = PlexServer(self.server_cnf["host"], self.server_cnf["token"])
            self.plex_libraies = self.pms.library.sections()
        except Exception as e:
            print(colored(f"[{current_time()}][ERROR-plex] Plex Media Server连接失败！{e}", "red"))
        self.path_mapping_rules = get_path_mapping_rules(self.server_cnf)

    def plex_find_libraries(self, path: Path, libraries):
        """
        判断这个path属于哪个媒体库
        多个媒体库配置的目录不应有重复和嵌套,
        """

        if path is None:
            return "", ""
        try:
            for lib in libraries:
                if hasattr(lib, "locations") and lib.locations:
                    for location in lib.locations:
                        if is_subpath(path, Path(location)):
                            if path.is_file():
                                # plex只支持刷新目录
                                path = path.parent
                            return lib.key, str(path)
        except Exception as err:
            print(f"[{current_time()}][ERROR-plex] 查找媒体库出错：{str(err)}")
        return "", ""

    # def plex_scan_specific_path(self, plex_libraies, directory):
    def scan_directory(self, directory):
        for rule in self.path_mapping_rules:
            if directory.startswith(rule[0]):
                directory = directory.replace(rule[0], rule[1], 1)
                break
        lib_key, path = self.plex_find_libraries(Path(directory), self.plex_libraies)
        if bool(lib_key) and bool(path):
            print(f"[{current_time()}][INFO-plex] 刷新媒体库：lib_key[{lib_key}] - path[{path}]")
            self.pms.query(f"/library/sections/{lib_key}/refresh?path={quote_plus(Path(path).as_posix())}")
        else:
            print(f"[{current_time()}][ERROR-plex] 未定位到媒体库：lib_key[{lib_key}] - path[{path}]")


# 参考https://github.com/NiNiyas/autoscan/blob/master/jelly_emby.py#L88
class EmbyScanner:
    def __init__(self, config) -> None:
        self.server_type = 'emby'
        self.server_cnf = config[self.server_type]
        self.host = self.server_cnf['host']
        self.api_key = self.server_cnf['api_key']
        self.path_mapping_rules = get_path_mapping_rules(self.server_cnf)

    def scan_directory(self, directory):
        for rule in self.path_mapping_rules:
            if directory.startswith(rule[0]):
                directory = directory.replace(rule[0], rule[1], 1)
                break
        data = {"Updates": [{"Path": f"{directory}", "UpdateType": "Created"}]}
        headers = {"accept": "application/json", "Content-Type": "application/json"}
        try:
            command = requests.post(
                self.host + f'/Library/Media/Updated?api_key={self.api_key}',
                headers=headers,
                json=data,
            )
            if command.status_code == 204:
                print(colored(f"[{current_time()}][INFO-emby] 刷新{self.server_type}中的：[{directory}]", "green"))
                pass
        except RequestException as e:
            print(colored(f"[{current_time()}][ERROR-emby] 刷新失败：path[{directory}]!", "red"))
            raise RequestException(colored(f"Error occurred when trying to send scan request to {self.server_type}. {e}", "red"))  # fmt: skip
