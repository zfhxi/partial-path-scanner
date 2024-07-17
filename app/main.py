import sys
import os
import yaml
import functools
import time
import multiprocessing as mp

# from threading import Thread
import threading
from concurrent.futures import ThreadPoolExecutor
from watchdog.observers.polling import PollingObserver
from watchdog.events import PatternMatchingEventHandler
import queue

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scanner import PlexScanner, EmbyScanner, getLogger, ScanType

logger = getLogger(__name__)


class UniqueQueue:
    def __init__(self):
        self.queue = queue.Queue()
        self.added_items = set()

    def put(self, item):
        if item not in self.added_items:
            self.queue.put(item)
            self.added_items.add(item)

    def get(self):
        item = self.queue.get()
        self.added_items.remove(item)
        return item

    def get_nowait(self):
        item = self.queue.get_nowait()
        self.added_items.remove(item)
        return item

    def empty(self):
        self.added_items.clear()
        return self.queue.empty()


class PathQueueThread(threading.Thread):
    """use a thread to process file path in a queue, avoid blocking the main thread
    refer to: https://github.com/vwvm/store/blob/37da0846f1a5a3712055d818e513d9d1e2b67379/python/backupCopy%E5%A4%87%E4%BB%BD/Watch.py#L168
    """

    def __init__(self, scanners, file_queue: queue.Queue, path_queue: UniqueQueue, event: threading.Event):
        super().__init__()
        self.scanners = scanners
        self.file_queue = file_queue
        self.path_queue = path_queue
        self.event = event
        worker_num = int(os.getenv("NUM_WORKERS", 1))
        logger.info(f"Launching a thread with a size {worker_num} to process file path in a queue!")
        self.pool_executor = ThreadPoolExecutor(max_workers=worker_num)

    def run(self) -> None:
        while not self.event.is_set():
            for scanner in self.scanners:
                try:
                    if scanner.scan_type == ScanType.FILE_BASED:
                        path = self.file_queue.get_nowait()
                    elif scanner.scan_type == ScanType.PATH_BASED:
                        path = self.path_queue.get_nowait()
                    else:
                        raise ValueError(f"Invalid scan type: {scanner.scan_type}")
                    self.pool_executor.submit(self.process, scanner, path, self.event)
                except queue.Empty:
                    time.sleep(10)

    def process(self, scanner, path, event):
        """
        while not event.is_set():
            try:
                scanner.scan_directory(path)
                break
            except Exception as e:
                logger.error(f"Failed to scan {path}!\n{e}")
                time.sleep(1)
        """
        scanner.scan_directory(path)


class FileChangeHandler(PatternMatchingEventHandler):
    def __init__(
        self,
        monitored_folders,
        scanners,
        stop_event: threading.Event,
        patterns=None,
        ignore_patterns=None,
        ignore_directories=False,
        case_sensitive=False,
    ):
        super().__init__(
            patterns=patterns,
            ignore_patterns=ignore_patterns,
            ignore_directories=ignore_directories,
            case_sensitive=case_sensitive,
        )
        self.monitored_folders = monitored_folders
        self.stop_event = stop_event
        # create a thread pool to process the file path
        self.file_queue = queue.Queue()
        self.path_queue = UniqueQueue()  # avoid duplicate path
        self.path_queue_thread = PathQueueThread(
            scanners=scanners,
            file_queue=self.file_queue,
            path_queue=self.path_queue,
            event=stop_event,
        )
        # setting the thread as daemon and start it
        self.path_queue_thread.daemon = True
        self.path_queue_thread.start()
        self.umount_flag = False

    def should_ignore(self, event):
        if '/.' in event.src_path or event.src_path in self.monitored_folders:
            return True
        else:
            return False

    def put_queue(self, path):
        self.file_queue.put(path)
        if os.path.isfile(path):
            self.path_queue.put(os.path.dirname(path))
        else:
            self.path_queue.put(path)

    def on_created(self, event):
        if self.should_ignore(event):
            return
        path = event.src_path
        logger.warning(f"[{event.event_type.upper()}][{path}]")
        self.put_queue(path)

    def on_deleted(self, event):
        if event.src_path in self.monitored_folders:
            logger.error(f"[{event.event_type.upper()}][{event.src_path}], possibly due to umount operation!")
            self.umount_flag = True
            return
        if self.should_ignore(event):
            return
        path = event.src_path
        logger.warning(f"[{event.event_type.upper()}][{path}]")
        self.put_queue(path)

    def on_modified(self, event):
        if True:
            return
        path = event.src_path
        logger.warning(f"[{event.event_type.upper()}][{path}]")
        self.path_queue.put(path)

    def on_moved(self, event):
        if self.should_ignore(event):
            return
        src_path = event.src_path
        dest_path = event.dest_path
        logger.warning(f"[{event.event_type.upper()}][from {src_path} to {dest_path}]")
        self.put_queue(src_path)
        self.put_queue(dest_path)


def read_config(yaml_fn):
    with open(yaml_fn, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
        servers = config['servers']
        for server in servers:
            assert server in ["emby", "plex"]
        return config


def monitoring_folder_func(idx, folder, monitored_folders, scanners):
    """create a observer to monitor the folder

    Args:
        idx (int): folder number
        folder (string): the absolute folder path
    """
    stop_event = threading.Event()
    event_handler = FileChangeHandler(
        monitored_folders=monitored_folders,
        scanners=scanners,
        stop_event=stop_event,
        ignore_patterns=None,
        ignore_directories=False,
    )
    logger.info(f"Folder{idx}[{folder}] monitor is launching...")
    observer = PollingObserver()
    observer.schedule(event_handler, folder, recursive=True)
    observer.start()
    observer.is_alive()
    logger.warning(f"Folder{idx}[{folder}] monitor is now active!")
    stopped = False
    try:
        while True:
            if event_handler.umount_flag:
                stop_event.set()
                observer.stop()
                observer.join()
                stopped = True
                event_handler.umount_flag = False
                logger.warning(f"Observer for folder{idx}[{folder}] is stopped!")
            else:
                if stopped:
                    observer = PollingObserver()
                    observer.schedule(event_handler, folder, recursive=True)
                    stop_event.clear()
                    observer.start()
                    stopped = False
                    event_handler.umount_flag = False
                    logger.warning(f"Observer for folder{idx}[{folder}] is re-activated!")

            # set a big sleep time to avoid high CPU usage
            # time.sleep(4294967)
            time.sleep(10)
    except KeyboardInterrupt:
        observer.stop()
        logger.info(f"Folder{idx}[{folder}] monitor is deactived!")
    observer.join()
    # close the thread pool
    event_handler.filepath_queue_thread.pool_executor.shutdown()


def launch(config):
    servers = config.get("servers")
    monitored_folders = config.get("MONITOR_FOLDER", [])
    scanners = []
    if 'plex' in servers:
        scanners.append(PlexScanner(config))
    if 'emby' in servers:
        scanners.append(EmbyScanner(config))

    monitoring_folder_wrapper = functools.partial(
        monitoring_folder_func, monitored_folders=monitored_folders, scanners=scanners
    )
    # build a process pool to monitor multiple folders
    POOL_SIZE = min(len(monitored_folders), os.cpu_count())
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
