import sys
import os
import yaml
import functools
import time
from termcolor import colored
import multiprocessing as mp
from watchdog.observers.polling import PollingObserver
from watchdog.events import PatternMatchingEventHandler

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scanner import PlexScanner, EmbyScanner, current_time


class FileChangeHandler(PatternMatchingEventHandler):
    def __init__(
        self,
        folders,
        scanners,
        patterns=None,
        ignore_patterns=None,
        ignore_directories=None,
        case_sensitive=False,
    ) -> None:
        super().__init__(
            patterns=patterns,
            ignore_patterns=ignore_patterns,
            ignore_directories=ignore_directories,
            case_sensitive=case_sensitive,
        )
        # 忽略隐藏文件夹
        self.folders = folders
        self.scanners = scanners

    def process(self, path):
        for scanner in self.scanners:
            scanner.scan_directory(path)

    def on_any_event(self, event):
        print(f'[{current_time()}][WARN] {event.event_type}[{event.src_path}]')
        self.process(event.src_path)


def read_config(yaml_fn):
    with open(yaml_fn, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
        servers = config['servers']
        for server in servers:
            assert server in ["emby", "plex"]
        return config


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

    event_handler = FileChangeHandler(
        folders=monitored_folders,
        scanners=scanners,
        ignore_patterns=[".*"],
        ignore_directories=True,
    )
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
