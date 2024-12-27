import os
from .pytimeparse import timeparse
from .others import timestamp_to_datetime, str2bool, read_deepvalue
from .logger import getLogger
from .scanner import PlexScanner, EmbyScanner, EmbyStrmScanner

from datetime import datetime
import functools
from collections import defaultdict

logger = getLogger(__name__)


class ScanningPool(object):
    def __init__(self, servers_cfg, storage_client, db, this_logger=logger):
        self.storage_client = storage_client
        self.db = db
        self.media_servers_cfg = servers_cfg
        self.pool = []
        self.wait_updating_mtimepaths = defaultdict(list)
        self.mtimepath2mtime = {}
        self.scanners = []
        self.init_scanners()
        self.logger = this_logger

    def init_scanners(self):
        self.scanners.clear()
        servers = self.media_servers_cfg.keys()
        if 'plex' in servers and str2bool(read_deepvalue(self.media_servers_cfg, 'plex', 'enabled')):
            self.scanners.append(PlexScanner(self.media_servers_cfg['plex']))
        if 'emby' in servers and str2bool(read_deepvalue(self.media_servers_cfg, 'emby', 'enabled')):
            self.scanners.append(EmbyScanner(self.media_servers_cfg['emby']))
        if 'embystrm' in servers and str2bool(read_deepvalue(self.media_servers_cfg, 'embystrm', 'enabled')):
            _scanner = EmbyStrmScanner(self.media_servers_cfg['embystrm'], self.storage_client.fs)
            self.scanners.append(_scanner)

    def put(self, mtime, mtime_path, sub_folders):
        if type(sub_folders) == list:
            self.pool.extend(sub_folders)
            self.wait_updating_mtimepaths[mtime_path].extend(sub_folders)
            # for sub_fd in sub_folders:
            # self.mtimepath2mtime[sub_fd] = mtime
        elif type(sub_folders) == str:
            self.pool.append(sub_folders)
            self.wait_updating_mtimepaths[mtime_path].append(sub_folders)
            # self.mtimepath2mtime[sub_folders] = mtime
        else:
            raise TypeError(f"Invalid path type: {type(sub_folders)}")
        self.mtimepath2mtime[mtime_path] = mtime

    def finish_scan(self):
        queue = set(self.pool)
        if len(queue) <= 0:
            return
        # 基于文件扫描的队列
        file_based_queue = list(queue)
        # 构建基于目录扫描的队列
        cache_isfile = defaultdict(lambda: False)
        cache_parent_folder = {}
        path_based_queue = []
        for _p in queue:
            if not self.storage_client.is_dir(_p):
                parent_of_p = os.path.dirname(_p)
                path_based_queue.append(parent_of_p)
                cache_isfile[_p] = True
                cache_parent_folder[_p] = parent_of_p
            else:
                path_based_queue.append(_p)
        path_based_queue = list(set(path_based_queue))
        # 构建目录是否被扫描的标记字典，默认为True
        mtimepath_scanned_marks = defaultdict(lambda: True)
        # 构建待扫描文件/子目录到mtimepath的映射
        sub_folder2mtimepath = {}
        for mtimepath, v in self.wait_updating_mtimepaths.items():
            # 去除重复的目录
            new_v = list(set(v))
            self.wait_updating_mtimepaths[mtimepath] = new_v
            # 构建子目录到mtimepath的映射
            for _v in new_v:
                sub_folder2mtimepath[_v] = mtimepath
                if cache_isfile[_v]:
                    sub_folder2mtimepath[cache_parent_folder[_v]] = mtimepath

        # 开始扫描
        for _scanner in self.scanners:
            self.logger.info(f"Scanning on {_scanner.server_type} media server...")
            if _scanner.isfile_based_scanning:
                for _f in file_based_queue:
                    rval = _scanner.scan_path(_f)
                    if not rval:
                        mtime_p = sub_folder2mtimepath[_f]
                        mtimepath_scanned_marks[mtime_p] = False
                        self.logger.error(f"扫描[{_f}]失败，将不更新目录[{mtime_p}]的mtime。")
                    else:
                        self.logger.warning(f"- {_f}")
            else:
                for _p in path_based_queue:
                    rval = _scanner.scan_path(_p)
                    if not rval:
                        mtime_p = sub_folder2mtimepath[_p]
                        mtimepath_scanned_marks[mtime_p] = False
                        self.logger.error(f"扫描[{_p}]失败，将不更新目录[{mtime_p}]的mtime!")
                    else:
                        self.logger.warning(f"- {_p}")
        for mtimepath in self.wait_updating_mtimepaths.keys():
            if mtimepath_scanned_marks[mtimepath] and not cache_isfile.get(
                mtimepath, False
            ):  # 如果mtimepath为文件，则不更新mtime
                _mtime = self.mtimepath2mtime[mtimepath]
                if _mtime:
                    self.db.set(mtimepath, _mtime)
                    self.logger.info(f"更新mtime: [{mtimepath}]=>{timestamp_to_datetime(_mtime)}")

        self.wait_updating_mtimepaths.clear()
        self.mtimepath2mtime.clear()
        self.pool.clear()


class ScanningPool4DeletedPaths(ScanningPool):
    def __init__(self, servers_cfg, storage_client, db, this_logger=logger):
        super().__init__(servers_cfg, storage_client, db, this_logger)
        _video_exts = servers_cfg.get('strm', {}).get('video_exts', [])
        _metadata_exts = servers_cfg.get('strm', {}).get('metadata_exts', [])
        self.known_file_exts = _video_exts + _metadata_exts

    def put(self, sub_folders):
        if type(sub_folders) == list:
            self.pool.extend(sub_folders)
        elif type(sub_folders) == str:
            self.pool.append(sub_folders)
        else:
            raise TypeError(f"Invalid path type: {type(sub_folders)}")

    def finish_scan(self):
        queue = set(self.pool)
        if len(queue) <= 0:
            return
        # 基于文件扫描的队列
        file_based_queue = list(queue)
        # 构建基于目录扫描的队列
        path_based_queue = []
        for _p in queue:
            ext = os.path.splitext(_p)[1]
            # FIXME: 通过splitext来粗略判断是否为文件夹，并不能百分百准确
            if ext == '' or ext not in self.known_file_exts:
                path_based_queue.append(_p)
            else:
                parent_of_p = os.path.dirname(_p)
                path_based_queue.append(parent_of_p)
        path_based_queue = list(set(path_based_queue))
        # 开始扫描
        for _scanner in self.scanners:
            self.logger.info(f"Scanning on {_scanner.server_type} media server...")
            if _scanner.isfile_based_scanning:
                for _f in file_based_queue:
                    rval = _scanner.scan_path(_f, deleted=True)
                    if not rval:
                        self.logger.error(f"扫描[{_f}]失败。")
                    else:
                        self.logger.warning(f"- {_f}")
            else:
                for _p in path_based_queue:
                    rval = _scanner.scan_path(_p, deleted=True)
                    if not rval:
                        self.logger.error(f"扫描[{_p}]失败。")
                    else:
                        self.logger.warning(f"- {_p}")
        self.pool.clear()


def path_scan_workder(
    path,
    find_updated_folders_func,
    scanning_pool,
    storage_client,
    db,
    fetch_mtime_only=False,
    fetch_all_mode=False,
    this_logger=logger,
):
    base_mtime = db.get(path)
    new_mtime = storage_client.get_mtime(path)
    if base_mtime is None or base_mtime != new_mtime:
        if not fetch_mtime_only:
            # 找出产生更新的子目录来进行扫库
            updated_folders = find_updated_folders_func(path)
            scanning_pool.put(new_mtime, path, updated_folders)
            # db.set(path, new_mtime)
        elif fetch_all_mode or base_mtime is None:
            db.set(path, new_mtime)
            # logger.info(f"Mtime of path[{path}] has been updated to {new_mtime}.")
            this_logger.info(f"更新mtime: [{path}]=>{timestamp_to_datetime(new_mtime)}")


def fs_walk(storage_client, top: str, blacklist=[], **kwargs):
    for path, dirs, _ in storage_client.walk_attr(top, topdown=True, **kwargs):
        _dirs = [
            d for d in dirs if not (d['path'] in blacklist or d['name'].startswith('.'))
        ]  # not valid when topdown=False
        dirs[:] = _dirs
        yield path, [a["name"] for a in dirs]


def find_updated_folders(top, blacklist, storage_client, db):
    '''找出哪个子目录或者文件变更了，只遍历一级深度（不进行向下递归）；
    比较子文件（夹）的mtime和top目录在数据库中的old_mtime，如果子文件（夹）的mtime大于top的old_mtime，则认为该子文件（夹）发生了变更；
    '''
    updated_folders = []
    subs = storage_client.listdir_attr(top)
    old_mtime = db.get(top)
    if bool(old_mtime):
        old_mtime = float(old_mtime)
        for sub in subs:
            sub_full_path = sub['path']
            if sub_full_path in blacklist or sub['name'].startswith("."):
                continue
            sub_mtime = float(storage_client.get_mtime(sub_full_path))
            if sub_mtime > old_mtime:
                updated_folders.append(sub_full_path)
                # BUG: 如果新增了folder，此处未将其mtime写入db，当下次遍历目录比对mtime时，会再次扫描该folder。此处摆烂，允许media server再次扫描。
    if len(updated_folders) == 0 and (storage_client.get_mtime(top) != str(old_mtime)):  # 可能删除了子文件（夹）
        updated_folders.append(top)
    return updated_folders


def folder_scan(
    _folder,
    _blacklist,
    servers_cfg,
    storage_client,
    db,
    fetch_mtime_only=False,
    fetch_all_mode=False,
    this_logger=logger,
):
    # config = YAMLCONFIG.get()
    # BEGIN OF MONITORING

    if not fetch_mtime_only:
        MODE = "遍历扫描"
    elif fetch_mtime_only and not fetch_all_mode:
        MODE = "mtime增量更新"
    else:
        MODE = "mtime全量更新"
    t_start = datetime.now()
    this_logger.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")  # fmt: skip
    this_logger.info(f"目录[{_folder}]的{MODE}@{t_start.replace(microsecond=0)}开始...")

    find_updated_folders_func = functools.partial(
        find_updated_folders,
        blacklist=_blacklist,
        storage_client=storage_client,
        db=db,
    )
    scanning_pool = ScanningPool(servers_cfg=servers_cfg, storage_client=storage_client, db=db, this_logger=this_logger)

    worker_partial = functools.partial(
        path_scan_workder,
        find_updated_folders_func=find_updated_folders_func,
        scanning_pool=scanning_pool,
        storage_client=storage_client,
        db=db,
        fetch_mtime_only=fetch_mtime_only,
        fetch_all_mode=fetch_all_mode,
        this_logger=this_logger,
    )
    # 监测子目录、子文件
    for root, _ in fs_walk(storage_client, top=_folder, blacklist=_blacklist):
        storage_client.listdir_attr(os.path.dirname(root))  # 对父目录进行listdir，确保top的mtime被更新
        worker_partial(root)
    try:
        scanning_pool.finish_scan()
    except Exception as e:
        this_logger.error(f"Error: {e}")

    # END OF MONITORING
    t_end = datetime.now()
    total_seconds = (t_end - t_start).total_seconds()
    if total_seconds < 60:
        this_logger.info(f"Time cost: {total_seconds:.2f} seconds!")
    else:
        total_minutes = total_seconds / 60
        this_logger.info(f"Time cost: {total_minutes:.2f} minutes!")
    this_logger.info(f"目录[{_folder}]的{MODE}@{t_end.replace(microsecond=0)}结束!")
    this_logger.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")  # fmt: skip


def create_folder_scheduler(
    monitored_folder,
    servers_cfg,
    scheduler,
    storage_client,
    db,
    fetch_mtime_only=False,
    fetch_all_mode=False,
):
    # folder_dict = YAMLCONFIG.get().get("MONITORED_FOLDERS", {})[folder]
    folder = monitored_folder.folder
    enabled = monitored_folder.enabled
    blacklist = monitored_folder.blacklist
    interval = monitored_folder.interval
    offset = monitored_folder.offset
    if enabled:
        # 获取目录的扫描间隔
        interval_secs = timeparse(interval)
        logger.info(f"目录[{folder}]启动监控中[间隔为: {interval}] ...")
        if offset > 0:
            jitter_secs = interval_secs * offset
        else:
            # job = schedule.every(schedule_interval_num).minutes.do(folder_scan, args, db, folder)
            jitter_secs = None
        scheduler.add_job(
            id=folder,
            func=folder_scan,
            trigger='interval',
            seconds=interval_secs,
            jitter=jitter_secs,
            args=[folder, blacklist, servers_cfg, storage_client, db, fetch_mtime_only, fetch_all_mode],
        )
        logger.info(f"目录[{folder}]的定时任务创建完成！")
    else:
        logger.info(f"目录[{folder}]未启用，不创建定时任务！")


def manual_scan(scan_path, servers_cfg, storage_client, db):
    scanning_pool = ScanningPool(servers_cfg=servers_cfg, storage_client=storage_client, db=db)
    '''扫描完指定路径后退出脚本'''
    logger.warning(f"Scanning path: {scan_path}...")
    mtime = storage_client.get_mtime(scan_path)
    scanning_pool.put(mtime, scan_path, scan_path)
    try:
        scanning_pool.finish_scan()
        return True, "扫描操作已触发，扫描结果见日志！"
    except Exception as e:
        logger.error(f"Error: {e}")
        return False, str(e)


def manual_scan_dest_pathlist(path_list, servers_cfg, storage_client, db, this_logger=logger):
    scanning_pool = ScanningPool(servers_cfg=servers_cfg, storage_client=storage_client, db=db, this_logger=this_logger)
    for p in path_list:
        mtime = storage_client.get_mtime(p)
        scanning_pool.put(mtime, p, p)
    try:
        scanning_pool.finish_scan()
    except Exception as e:
        this_logger.error(f"Error: {e}")


def manual_scan_deleted_pathlist(path_list, servers_cfg, storage_client, db, this_logger=logger):
    scanning_pool = ScanningPool4DeletedPaths(
        servers_cfg=servers_cfg, storage_client=storage_client, db=db, this_logger=this_logger
    )
    _knwon_file_exts = scanning_pool.known_file_exts
    for p in path_list:
        ext = os.path.splitext(p)[1]
        # FIXME: 通过splitext来粗略判断是否为文件夹，并不能百分百准确
        if ext == '' or ext not in _knwon_file_exts:
            db.delete(p)
        scanning_pool.put(p)
    try:
        scanning_pool.finish_scan()
    except Exception as e:
        this_logger.error(f"Error: {e}")
