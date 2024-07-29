import os
import yaml
import psutil
import coloredlogs, logging
from datetime import datetime

# Suppress logging warnings, refer to https://stackoverflow.com/questions/78780089/how-do-i-get-rid-of-the-annoying-terminal-warning-when-using-gemini-api
os.environ["GRPC_VERBOSITY"] = "ERROR"
# os.environ["GLOG_minloglevel"] = "2"


def load_yaml_config(yaml_fn):
    with open(yaml_fn, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
        servers = config['servers']
        for server in servers:
            assert server in ["emby", "plex"]
        return config


def str2bool(v):
    if isinstance(v, bool):
        return v
    elif v in ["True", "true", "1"]:
        return True
    elif v in ["False", "false", "0"]:
        return False
    else:
        raise ValueError("Boolean value expected.")


def current_time():
    return datetime.now().replace(microsecond=0)


def get_other_pids_by_script_name(script_name):
    pids = []
    mypid = os.getpid()
    for process in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd_line = process.info['cmdline']
            cmd_str = ' '.join(cmd_line) if cmd_line else ''
            pid = process.info['pid']
            if script_name in cmd_str and pid != mypid:
                pids.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return pids


# refer to:
# https://vra.github.io/2019/09/10/colorful-logging/
COLOR_FIELD_STYLES = dict(
    asctime=dict(color='green'),
    hostname=dict(color='magenta'),
    levelname=dict(color='green'),
    filename=dict(color='magenta'),
    name=dict(color='blue'),
    threadName=dict(color='green'),
)

COLOR_LEVEL_STYLES = dict(
    debug=dict(color='green'),
    info=dict(color='cyan'),
    warning=dict(color='yellow'),
    error=dict(color='red'),
    critical=dict(color='red'),
)
coloredlogs.install(
    level="DEBUG",
    isatty=True,
    fmt="[%(levelname)s] [%(asctime)s] [%(filename)s:%(lineno)d] %(message)s",
    level_styles=COLOR_LEVEL_STYLES,
    field_styles=COLOR_FIELD_STYLES,
)


def getLogger(name):
    return logging.getLogger(name)
