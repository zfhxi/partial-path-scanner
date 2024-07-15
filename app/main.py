import sys
import os
import yaml
import functools
import time
import multiprocessing as mp
from threading import Thread
from watchdog.observers.polling import PollingObserver
from watchdog.events import PatternMatchingEventHandler

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scanner import PlexScanner, EmbyScanner, getLogger

logger = getLogger(__name__)


class FileChangeHandler(PatternMatchingEventHandler):
    def __init__(
        self,
        folders,
        scanners,
        patterns=None,
        ignore_patterns=None,
        ignore_directories=None,
        case_sensitive=False,
    ):
        super().__init__(
            patterns=patterns,
            ignore_patterns=ignore_patterns,
            ignore_directories=ignore_directories,
            case_sensitive=case_sensitive,
        )
        self.folders = folders
        self.scanners = scanners

    def process(self, path):
        for scanner in self.scanners:
            scanner.scan_directory(path)

    def on_any_event(self, event):
        logger.warning(f"[{event.event_type.upper()}][{event.src_path}]")
        thread = Thread(target=self.process, args=(event.src_path,))
        thread.start()


def read_config(yaml_fn):
    with open(yaml_fn, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
        servers = config['servers']
        for server in servers:
            assert server in ["emby", "plex"]
        return config


def monitoring_folder_func(idx, folder, event_handler):
    """create a observer to monitor the folder

    Args:
        idx (int): folder number
        folder (string): the absolute folder path
        event_handler : the event handler
    """
    logger.info(f"Folder{idx}[{folder}] monitor is launching...")
    observer = PollingObserver()
    observer.schedule(event_handler, folder, recursive=True)
    observer.start()
    logger.info(f"Folder{idx}[{folder}] monitor is now active!")
    try:
        while True:
            # set a big sleep time to avoid high CPU usage
            time.sleep(4294967)
    except KeyboardInterrupt:
        observer.stop()
        logger.info(f"Folder{idx}[{folder}] monitor is deactived!")
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
    # build a process pool to monitor multiple folders
    POOL_SIZE = int(os.getenv("POOL_SIZE", 1))
    logger.info(f"Launching a pool with a size {POOL_SIZE}!")
    pool = mp.Pool(POOL_SIZE)

    for idx, _folder in enumerate(monitored_folders):
        pool.apply_async(monitoring_folder_wrapper, args=(idx + 1, _folder))
    pool.close()
    pool.join()


if __name__ == "__main__":
    logger.info(f"\n####################################################################################################")  # fmt: skip
    logger.info(f"Start to monitoring folders...")
    CONFIG_FILE = os.getenv("CONFIG_FILE", "./config/config.yaml")
    try:
        config = read_config(CONFIG_FILE)
        launch(config)
    except Exception as e:
        logger.error(f"Failed to monitor or refresh folders！")
        logger.error(e)
    finally:
        pass
    logger.warning(f"End of monitoring folders!")
    logger.info(f"####################################################################################################")
