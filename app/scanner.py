from pathlib import Path
from plexapi.server import PlexServer
from urllib.parse import quote_plus
import requests
from datetime import datetime
from requests import RequestException
import coloredlogs, logging


# 参考：https://vra.github.io/2019/09/10/colorful-logging/
COLOR_FIELD_STYLES = dict(
    asctime=dict(color='green'),
    hostname=dict(color='magenta'),
    levelname=dict(color='green'),
    filename=dict(color='magenta'),
    name=dict(color='blue'),
    threadName=dict(color='green'),
)

COLOR_LEVEL_STYLES = dict(
    debug=dict(color='green'),
    info=dict(color='cyan'),
    warning=dict(color='yellow'),
    error=dict(color='red'),
    critical=dict(color='red'),
)
coloredlogs.install(
    level="DEBUG",
    isatty=True,
    fmt="[%(levelname)s] [%(asctime)s] [%(filename)s:%(lineno)d] %(message)s",
    level_styles=COLOR_LEVEL_STYLES,
    field_styles=COLOR_FIELD_STYLES,
)


def getLogger(name):
    return logging.getLogger(name)


logger = getLogger(__name__)


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
            logger.info(f"Plex Media Server连接失败！{e}")
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
            logger.error(f"查找媒体库出错：{str(err)}")
        return "", ""

    # def plex_scan_specific_path(self, plex_libraies, directory):
    def scan_directory(self, directory):
        for rule in self.path_mapping_rules:
            if directory.startswith(rule[0]):
                directory = directory.replace(rule[0], rule[1], 1)
                break
        lib_key, path = self.plex_find_libraries(Path(directory), self.plex_libraies)
        if bool(lib_key) and bool(path):
            logger.info(f"刷新媒体库：lib_key[{lib_key}] - path[{path}]")
            self.pms.query(f"/library/sections/{lib_key}/refresh?path={quote_plus(Path(path).as_posix())}")
        else:
            logger.error(f"未定位到媒体库：lib_key[{lib_key}] - path[{path}]")


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
                logger.info(f"刷新{self.server_type}中的：[{directory}]")
                pass
        except RequestException as e:
            logger.info(f"刷新失败：path[{directory}]!")
            raise RequestException(f"Error occurred when trying to send scan request to {self.server_type}. {e}")
