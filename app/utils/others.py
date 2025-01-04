from datetime import datetime
import time


def read_deepvalue(data, *keys):
    """
    :param data: dict
    :param keys: multiple keys
    """
    _data = data
    for k in keys:
        _data = _data.get(k, {})
    return _data


def str2bool(v):
    if isinstance(v, bool):
        return v
    elif str(v).lower() in ["true", "1"]:
        return True
    elif str(v).lower() in ["false", "0", ""] or (bool(v) is False):
        return False
    else:
        raise ValueError("Boolean value expected.")


def timestamp_to_datetime(timestamp):
    if type(timestamp) == str:
        timestamp = float(timestamp)
    # 转换成localtime
    time_local = time.localtime(timestamp)
    # 转换成新的时间格式(2016-05-05 20:28:54)
    dt = time.strftime("%Y-%m-%d %H:%M:%S", time_local)
    return dt


def current_time():
    return datetime.now().replace(microsecond=0)
