import os, sys
from pathlib import Path
from plexapi.server import PlexServer
from urllib.parse import quote_plus
import requests
from requests import RequestException

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import getLogger


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
    path_mapping_enable = path_mapping.get('enable', False)
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
        self.server_cnf = config["plex"]
        try:
            self.pms = PlexServer(self.server_cnf["host"], self.server_cnf["token"])
            self.plex_libraies = self.pms.library.sections()
        except Exception as e:
            logger.error(f"[PLEX] Failed to connect to the Plex Media Server!\n{e}")
        self.path_mapping_rules = get_path_mapping_rules(self.server_cnf)

    def plex_find_libraries(self, path: Path, libraries):
        """
        Determine which media this path belongs to.
        """

        if path is None:
            return "", "", ""
        try:
            for lib in libraries:
                if hasattr(lib, "locations") and lib.locations:
                    for location in lib.locations:
                        if is_subpath(path, Path(location)):
                            if path.is_file():
                                # plex media server only supports refreshing folders not files
                                path = path.parent
                            return lib.key, lib.title, str(path)
        except Exception as err:
            logger.error(f"[PLEX] Unable to find a library for the path[{path.as_posix()}]\n{err}")
        return "", "", ""

    # def plex_scan_specific_path(self, plex_libraies, directory):
    def scan_directory(self, directory, **kwargs):
        for rule in self.path_mapping_rules:
            if directory.startswith(rule[0]):
                directory = directory.replace(rule[0], rule[1], 1)
                break
        lib_key, lib_title, path = self.plex_find_libraries(Path(directory), self.plex_libraies)
        if bool(lib_key) and bool(path):
            logger.info(f"[PLEX] Scanning the library[{lib_title}] - path[{path}]")
            self.pms.query(f"/library/sections/{lib_key}/refresh?path={quote_plus(Path(path).as_posix())}")
        else:
            logger.error(f"[PLEX] Unable to find a library for the path[{path}]!")


# refer to:
# https://github.com/NiNiyas/autoscan/blob/master/jelly_emby.py#L88
class EmbyScanner:
    def __init__(self, config) -> None:
        self.server_type = 'emby'
        self.server_cnf = config[self.server_type]
        self.host = self.server_cnf['host']
        self.api_key = self.server_cnf['api_key']
        self.path_mapping_rules = get_path_mapping_rules(self.server_cnf)

    def scan_directory(self, directory, **kwargs):
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
                logger.info(f"[{self.server_type.upper()}] Scanning the path[{directory}]")
                pass
        except RequestException as e:
            logger.error(f"Failed to refresh the path[{directory}]!")
            raise RequestException(f"Error occurred when trying to send scan request to {self.server_type}. {e}")
