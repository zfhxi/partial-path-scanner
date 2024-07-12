import os
import multiprocessing as mp
from threading import Thread
import concurrent.futures


def custom_only_scan_dir(path, exclude_dirs=[]):
    if path in exclude_dirs:
        return
    if os.path.split(path)[1].startswith('.'):
        return
    for entry in os.scandir(path):
        if entry.is_dir():
            if entry.path in exclude_dirs or entry.name.startswith('.'):
                continue
            yield entry.path
            yield from custom_only_scan_dir(entry.path, exclude_dirs)


def os_walk_bylevel_only_dir(some_dir, exclude_dirs=[], level=1):
    some_dir = some_dir.rstrip(os.path.sep)
    assert os.path.isdir(some_dir)
    num_sep = some_dir.count(os.path.sep)
    for root, dirs, files in os.walk(some_dir):
        if root in exclude_dirs or os.path.basename(root).startswith('.'):
            del dirs[:]
            continue
        elif root.rstrip(os.path.sep) == some_dir:
            continue
        else:
            if root.count(os.path.sep) - num_sep >= level:
                del dirs[:]
            yield root


def custom_only_scan_dir_wraper(x, exclude_dirs):
    return list(custom_only_scan_dir(x, exclude_dirs))


def parallel_walker_mt(path, exclude_dirs=[], level=1):
    """递归遍历目录 多线程版

    Args:
        path (_type_): _description_
        exclude_dirs (list, optional): _description_. Defaults to [].
        level (int, optional): _description_. Defaults to 1.

    Returns:
        _type_: _description_
    """
    _dirs = []
    sep = os.path.sep
    num_sep = path.rstrip(sep).count(sep)
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.getenv("MAX_WORKERS", 4)) as executor:
        todo = []
        for sub_path in os_walk_bylevel_only_dir(path, exclude_dirs=exclude_dirs, level=level):
            if sub_path in exclude_dirs or os.path.basename(sub_path).startswith('.'):
                continue
            this_num_sep = sub_path.rstrip(sep).count(sep)
            _dirs.append(sub_path)
            if this_num_sep - num_sep >= level:
                future = executor.submit(custom_only_scan_dir, sub_path, exclude_dirs)
                todo.append(future)
    for future in concurrent.futures.as_completed(todo):
        _dirs.extend(future.result())
    return _dirs


def parallel_walker_mp(path, exclude_dirs=[], level=1, poolsize=1):
    """递归遍历目录 多进程版

    Args:
        path (_type_): _description_
        exclude_dirs (list, optional): _description_. Defaults to [].
        level (int, optional): _description_. Defaults to 1.
        poolsize (int, optional): _description_. Defaults to 1.

    Returns:
        _type_: _description_
    """
    _dirs = []
    sep = os.path.sep
    num_sep = path.rstrip(sep).count(sep)
    results = []
    pool = mp.Pool(poolsize)
    for sub_path in os_walk_bylevel_only_dir(path, exclude_dirs=exclude_dirs, level=level):
        if sub_path in exclude_dirs or os.path.basename(sub_path).startswith('.'):
            continue
        this_num_sep = sub_path.rstrip(sep).count(sep)
        _dirs.append(sub_path)
        if this_num_sep - num_sep >= level:
            res = pool.apply_async(custom_only_scan_dir_wraper, (sub_path, exclude_dirs))
            results.append(res)
    pool.close()
    pool.join()
    for res in results:
        _dirs.extend(res.get())
    return _dirs
