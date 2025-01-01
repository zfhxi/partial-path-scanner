import os, sys, time
import shutil
from pathlib import Path
from plexapi.server import PlexServer
from urllib.parse import quote_plus
import requests
from requests import RequestException
from app.utils import getLogger
import concurrent.futures
from clouddrive import CloudDrivePath

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
# https://github.com/tanlidoushen/CloudDriveAlistEmbyScripts/blob/main/webhook_strm/sha1-strm-%E5%AE%8C%E6%95%B4%E8%B7%AF%E5%BE%84-url%E8%BD%AC%E7%A0%81.py
class StrmProcessor:
    def __init__(self, strm_config, fs) -> None:
        self.strm_cnf = strm_config
        self.max_workers = int(self.strm_cnf.get("max_workers", 1))
        self.video_exts = self.strm_cnf.get("video_exts", [])
        self.metadata_exts = self.strm_cnf.get("metadata_exts", [])
        self.enable_copy_metadata = self.strm_cnf.get("enable_copy_metadata", False)
        self.enable_clean_invalid_strm = self.strm_cnf.get("enable_clean_invalid_strm", False)
        self.enable_clean_invalid_folders = self.strm_cnf.get("enable_clean_invalid_folders", False)
        self.enable_clean_invalid_metadata = self.strm_cnf.get("enable_clean_invalid_metadata", False)
        self.strm_root_mapping_rules = self.get_strm_root_mapping_rules()
        self.generated_strm_files = set()
        self.fs = fs
        self.known_file_exts = self.video_exts + self.metadata_exts

    def get_strm_root_mapping_rules(self):
        rule_set = []
        mapping_rules = self.strm_cnf.get('root_mapping', [])
        for rule in mapping_rules:
            rule_set.append((rule.get('src', ''), rule.get('dest', ''), rule.get('mount', '')))
        return rule_set

    def process_file(self, file_path, src_root, dest_root, mount_root):
        file_extension = os.path.splitext(file_path)[1].lower()
        # 获取strm文件/元数据文件的目标目录
        target_path = os.path.dirname(file_path).replace(src_root, dest_root, 1)
        # 判断是strm文件还是元数据文件
        if file_extension in self.video_exts:
            os.makedirs(target_path, exist_ok=True)
            strm_file_path = os.path.join(target_path, os.path.splitext(os.path.basename(file_path))[0] + '.strm')
            # 标准化路径
            strm_file_path = os.path.normpath(strm_file_path)
            # strm文件中的内容为本地挂载cd2后的路径
            mount_file_path = file_path.replace(src_root, mount_root, 1)

            if os.path.exists(strm_file_path):
                with open(strm_file_path, 'r', encoding='utf-8') as existing_strm:
                    existing_url = existing_strm.read().strip()
                if existing_url == mount_file_path:
                    self.generated_strm_files.add(strm_file_path)
                    return True  # "存在strm文件，跳过生成"

            with open(strm_file_path, 'w', encoding='utf-8') as strm_file:
                strm_file.write(mount_file_path)
                self.generated_strm_files.add(strm_file_path)
                logger.info(f"生成.strm文件: {strm_file_path}")
            return True  # "已生成strm文件"

        elif self.enable_copy_metadata and file_extension in self.metadata_exts:
            os.makedirs(target_path, exist_ok=True)
            target_file_path = os.path.join(target_path, os.path.basename(file_path))
            if not os.path.exists(target_file_path):
                self.fs.download(file_path, target_file_path)
                logger.info(f"复制文件: {file_path} -> {target_file_path}")
                return False  # "复制元数据文件"

    def process_deleting_file(self, file_path, src_root, dest_root, mount_root):
        # logger.warning(f"处理文件: {file_path}")
        file_extension = os.path.splitext(file_path)[1].lower()
        # 获取strm文件/元数据文件的目标目录
        target_path = os.path.dirname(file_path).replace(src_root, dest_root, 1)
        # 判断是strm文件还是元数据文件
        if file_extension in self.video_exts:
            os.makedirs(target_path, exist_ok=True)
            strm_file_path = os.path.join(target_path, os.path.splitext(os.path.basename(file_path))[0] + '.strm')
            # 标准化路径
            strm_file_path = os.path.normpath(strm_file_path)
            os.remove(strm_file_path)
            return True  # "已生成strm文件"

        elif self.enable_copy_metadata and file_extension in self.metadata_exts:
            target_file_path = os.path.join(target_path, os.path.basename(file_path))
            if os.path.exists(target_file_path):
                os.remove(target_file_path)

    def cleanup_invalid_strm(self, net_folder, strm_folder):
        logger.warning("开始清理失效的.strm文件...")
        for root, _, files in os.walk(strm_folder):
            for file in files:
                if file.endswith('.strm'):
                    strm_file_path = os.path.normpath(os.path.join(root, file))
                    _need_deleted = True
                    if strm_file_path in self.generated_strm_files:  # 如果刚才已生产此strm文件
                        _need_deleted = False
                    else:  # 如果刚才没生成strm文件，但有可能其他线程监听时生成了该strm文件
                        try:
                            with open(strm_file_path, 'r', encoding='utf-8') as existing_strm:
                                existing_url = existing_strm.read().strip()
                                net_file_path = strm_file_path.replace(".strm", os.path.splitext(existing_url)[1], 1)
                                net_file_path = net_file_path.replace(strm_folder, net_folder, 1)
                                if self.fs.exists(net_file_path):
                                    _need_deleted = False
                        except Exception as e:
                            logger.error(f"检测strm有效性失败！{e}")
                            _need_deleted = False
                    if _need_deleted:
                        os.remove(strm_file_path)
                        logger.info(f"删除失效的.strm文件: {strm_file_path}")

    def cleanup_invalid_folders(self, src_folder, dest_folder):
        logger.warning("开始清理失效的文件夹...")
        for root, dirs, _ in os.walk(dest_folder, topdown=False):
            for _dir in dirs:
                target_dir_path = os.path.normpath(os.path.join(root, _dir))
                source_dir_path = target_dir_path.replace(dest_folder, src_folder, 1)
                if not self.fs.exists(source_dir_path):
                    shutil.rmtree(target_dir_path)
                    logger.info(f"删除失效的文件夹: {target_dir_path}")

    def cleanup_invalid_metadata(self, src_folder, dest_folder):
        logger.warning("开始清理失效的元数据文件...")
        for root, _, files in os.walk(dest_folder):
            for file in files:
                file_extension = os.path.splitext(file)[1].lower()
                if file_extension in self.metadata_exts:
                    target_file_path = os.path.normpath(os.path.join(root, file))
                    # 从strm路径映射回cd2中的路径
                    source_file_path = target_file_path.replace(dest_folder, src_folder, 1)
                    if not self.fs.exists(source_file_path):
                        os.remove(target_file_path)
                        logger.info(f"删除失效的元数据文件: {target_file_path}")

    def clean_invalid(self, src_folder, dest_folder):
        if self.enable_clean_invalid_strm:
            self.cleanup_invalid_strm(src_folder, dest_folder)

        if self.enable_clean_invalid_folders:
            self.cleanup_invalid_folders(src_folder, dest_folder)

        if self.enable_clean_invalid_metadata:
            self.cleanup_invalid_metadata(src_folder, dest_folder)

    def fs_walk_files(self, top: str, blacklist=[], **kwargs):
        for _, dirs, files in self.fs.walk_attr(top, topdown=True, **kwargs):
            _dirs = [
                d for d in dirs if not (d['path'] in blacklist or d['name'].startswith('.'))
            ]  # not valid when topdown=False
            dirs[:] = _dirs
            yield [CloudDrivePath(self.fs, **a) for a in files]

    def run(self, path, **kwargs):
        logger.warning(f"开始处理路径: {path}...")
        self.generated_strm_files.clear()
        # 从strm路径映射回cd2中的路径
        deleted = kwargs.get('deleted', False)
        src_folder = path
        dest_folder = path
        mount_folder = path
        for rule in self.strm_root_mapping_rules:
            if dest_folder.startswith(rule[0]):
                dest_folder = dest_folder.replace(rule[0], rule[1], 1)
                mount_folder = mount_folder.replace(rule[0], rule[2], 1)
                break
        # if not self.fs.attr(path)['isDirectory']:  # 如果是文件
        # FIXME: 通过splitext来粗略判断是否为文件夹，并不能百分百准确
        ext = os.path.splitext(path)[1]
        if ext == '' or ext not in self.known_file_exts:  # 如果是文件夹
            if deleted:
                need_deleting_path = path.replace(src_folder, dest_folder, 1)
                shutil.rmtree(need_deleting_path)
                logger.info(f"清理失效路径：{need_deleting_path}")
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    for files in self.fs_walk_files(src_folder):
                        for file in files:
                            file_path = file.fullPathName
                            executor.submit(self.process_file, file_path, src_folder, dest_folder, mount_folder)
            # 清理失效文件（夹）
            self.clean_invalid(src_folder, dest_folder)
        else:  # 如果是文件
            src_folder = os.path.dirname(src_folder)
            dest_folder = os.path.dirname(dest_folder)
            mount_folder = os.path.dirname(mount_folder)
            if deleted:
                self.process_deleting_file(path, src_folder, dest_folder, mount_folder)
            else:
                self.process_file(path, src_folder, dest_folder, mount_folder)

        logger.info("处理完成！")


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


class EmbyStrmScanner(EmbyScanner):
    def __init__(self, config, fs) -> None:
        super().__init__(config)
        self.server_type = 'embystrm'
        self.strm_processor = StrmProcessor(config['strm'], fs)

    def scan_path(self, path: str, **kwargs) -> bool:
        self.strm_processor.run(path, **kwargs)
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
                return True
            else:
                logger.error(f"Failed to scan the path[{path}]!")
                return False
        except RequestException as e:
            logger.error(f"Failed to refresh the path[{path}]!\n{e}")
            return False
