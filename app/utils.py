import os
import psutil
import yaml


def str2bool(v):
    if isinstance(v, bool):
        return v
    elif v in ["True", "true", "1"]:
        return True
    elif v in ["False", "false", "0"]:
        return False
    else:
        raise ValueError("Boolean value expected.")


def read_config(yaml_fn):
    with open(yaml_fn, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
        servers = config['servers']
        for server in servers:
            assert server in ["emby", "plex"]
        return config


def get_pids_by_name(keyword, exclude_self=True):
    """根据关键字寻找进程的pid
    Args:
        keyword (_type_): 启动进程命令的的关键字
        exclude_self (bool, optional): 是否返回进程自身的pid. Defaults to True.

    Returns:
        list: 进程的pid列表
    """

    pids = []
    mypid = os.getpid()
    for process in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd_line = process.info['cmdline']
            cmd_str = ' '.join(cmd_line) if cmd_line else ''
            pid = process.info['pid']
            if keyword in cmd_str:
                if pid != mypid or not exclude_self:
                    pids.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return pids
