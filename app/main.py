import sys
import os
import yaml
import functools
import time
from datetime import datetime
from termcolor import colored
import multiprocessing as mp
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scanner import PlexScanner, EmbyScanner


def current_time():
    return datetime.now().replace(microsecond=0)


class FileChangeHandler(FileSystemEventHandler):
    """_summary_

    Args:
        FileSystemEventHandler (_type_): _description_
    """

    def __init__(self, func, folders) -> None:
        super().__init__()
        self.func = func
        self.folders = folders

    def should_ignore(self, path):
        if path in self.folders:
            # 不刷新顶级监测目录
            print(f"[{current_time()}][WARN] 忽略处理：{path}，原因：不刷新顶级目录[{path}]！")
            return True
        root_folder = ""
        for p in self.folders:
            if path.startswith(p):
                root_folder = p
                break

        if bool(root_folder) and not os.path.exists(root_folder):
            # 最顶级的监测目录发生变动，但是不存在了（可能挂载点被卸载了、或被删除），忽略处理
            print(f"[{current_time()}][WARN] 忽略处理：{path}，原因：监控目录[{root_folder}]似乎被卸载/删除！")
            return True

    def on_modified(self, event):
        if not self.should_ignore(event.src_path):
            print(f'[{current_time()}][WARN] 修改[{event.src_path}]')
            self.func(event.src_path)

    def on_created(self, event):
        if not self.should_ignore(event.src_path):
            print(f'[{current_time()}][WARN] 创建[{event.src_path}]')
            self.func(event.src_path)

    def on_deleted(self, event):
        if not self.should_ignore(event.src_path):
            # TODO: 调用plexapi
            print(f'[{current_time()}][WARN] 删除[{event.src_path}]')
            self.func(event.src_path)

    def on_moved(self, event):
        if not self.should_ignore(event.src_path):
            '''似乎文件的移动也被认为是从一个文件夹删除到另一个文件夹创建'''
            print(f"[{current_time()}][WARN] 移动[{event.src_path}]到[{event.dest_path}]")


def read_config(yaml_fn):
    with open(yaml_fn, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
        servers = config['servers']
        for server in servers:
            assert server in ["emby", "plex"]
        return config


def scanning_callback(path, scanners):
    """回调函数，传给监听器，当文件发生变化时调用

    Args:
        scanners (list): 多个scanner
        path (string): 变化的文件/文件夹路径
    """
    for scanner in scanners:
        scanner.scan_directory(path)


def monitoring_folder_func(idx, folder, event_handler):
    print(colored(f"[{current_time()}][INFO] 目录{idx}[{folder}]监测启动...", "cyan"))
    observer = PollingObserver()
    observer.schedule(event_handler, folder, recursive=True)
    observer.start()
    print(colored(f"[{current_time()}][INFO] 目录{idx}[{folder}]监测启动完成！", "green"))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print(colored(f"[{current_time()}][ERROR] 目录{idx}[{folder}]监测取消！", "red"))
    observer.join()


def launch(config):
    servers = config.get("servers")
    monitored_folders = config.get("MONITOR_FOLDER", [])
    scanners = []
    if 'plex' in servers:
        scanners.append(PlexScanner(config))
    if 'emby' in servers:
        scanners.append(EmbyScanner(config))
    # 包装回调函数
    worker_callback = functools.partial(scanning_callback, scanners=scanners)
    event_handler = FileChangeHandler(worker_callback, monitored_folders)
    monitoring_folder_wrapper = functools.partial(monitoring_folder_func, event_handler=event_handler)
    # 构建进程池
    POOL_SIZE = int(os.getenv("POOL_SIZE", 1))
    print(colored(f"[{current_time()}][INFO] 启动进程池，大小：{POOL_SIZE}", "cyan"))
    pool = mp.Pool(POOL_SIZE)

    for idx, _folder in enumerate(monitored_folders):
        pool.apply_async(monitoring_folder_wrapper, args=(idx + 1, _folder))
    pool.close()
    pool.join()


if __name__ == "__main__":
    print(f"\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    print(colored(f"[{current_time()}][INFO] 开始监测...", "green"))
    CONFIG_FILE = os.getenv("CONFIG_FILE", "./config/config.yaml")
    try:
        config = read_config(CONFIG_FILE)
        launch(config)
    except Exception as e:
        print(colored(f"[{current_time()}][ERROR] 监测or刷新失败！", "red"))
        print(e)
    finally:
        pass
    print(colored(f"[{current_time()}][WARN] 结束监测   ", "green"))
    print(f"<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
