#
# 第一个参数，bool类型，是否只初始化数据库，不扫描
#
import sys
import os
import yaml
import functools
import time
from termcolor import colored
import multiprocessing as mp
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scanner import PlexScanner, EmbyScanner


class FileChangeHandler(FileSystemEventHandler):
    """_summary_

    Args:
        FileSystemEventHandler (_type_): _description_
    """

    def __init__(self, func) -> None:
        super().__init__()
        self.func = func

    def on_modified(self, event):
        print(f'文件被修改: {event.src_path}')
        self.func(event.src_path)

    def on_created(self, event):
        print(f'新文件/目录创建: {event.src_path}')
        self.func(event.src_path)

    def on_deleted(self, event):
        # TODO: 调用plexapi
        print(f'文件/目录被删除: {event.src_path}')
        self.func(event.src_path)

    def on_moved(self, event):
        '''似乎文件的移动也被认为是从一个文件夹删除到另一个文件夹创建'''
        print(f"文件/目录被移动: 从{event.src_path}到{event.dest_path}")


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


def monitor_folder(idx, folder, event_handler):
    print(colored(f"[INFO] 目录{idx}[{folder}]监测启动...", "cyan"))
    observer = PollingObserver()
    observer.schedule(event_handler, folder, recursive=True)
    observer.start()
    print(colored(f"[INFO] 目录{idx}[{folder}]监测启动完成！", "green"))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print(colored(f"[ERROR] 目录{idx}[{folder}]监测取消！", "red"))
    observer.join()


def launch(config):
    servers = config.get("servers")
    scanners = []
    if 'plex' in servers:
        scanners.append(PlexScanner(config))
    if 'emby' in servers:
        scanners.append(EmbyScanner(config))
    # 包装回调函数
    worker_callback = functools.partial(scanning_callback, scanners=scanners)
    event_handler = FileChangeHandler(worker_callback)
    monitor_folder_wrapper = functools.partial(monitor_folder, event_handler=event_handler)
    # 构建进程池
    POOL_SIZE = int(os.getenv("POOL_SIZE", 1))
    print(colored(f"启动进程池，大小：{POOL_SIZE}", "cyan"))
    pool = mp.Pool(POOL_SIZE)

    monitored_folders = config.get("MONITOR_FOLDER", [])
    for idx, _folder in enumerate(monitored_folders):
        pool.apply_async(monitor_folder_wrapper, args=(idx, _folder))
    pool.close()
    pool.join()


if __name__ == "__main__":
    print(f"\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    print(colored(f"开始监测...", "green"))
    CONFIG_FILE = os.getenv("CONFIG_FILE", "./config/config.yaml")
    try:
        config = read_config(CONFIG_FILE)
        launch(config)
    except Exception as e:
        print(colored("[ERROR] 监测or刷新失败！", "red"))
        print(e)
    finally:
        pass
    print(colored(f"结束监测   ", "green"))
    print(f"<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
