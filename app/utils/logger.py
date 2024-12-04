import os
import coloredlogs, logging

# Suppress logging warnings, refer to https://stackoverflow.com/questions/78780089/how-do-i-get-rid-of-the-annoying-terminal-warning-when-using-gemini-api
os.environ["GRPC_VERBOSITY"] = "ERROR"
# os.environ["GLOG_minloglevel"] = "1"
# os.environ["GLOG_minloglevel"] = "true"

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
formatter_string = "[%(levelname)s] [%(asctime)s] [%(filename)s:%(lineno)d] %(message)s"
coloredlogs.install(
    # level="DEBUG",
    level="INFO",
    isatty=True,
    fmt=formatter_string,
    level_styles=COLOR_LEVEL_STYLES,
    field_styles=COLOR_FIELD_STYLES,
)


# https://stackoverflow.com/questions/879732/logging-with-filters
class FileHandlerFilter(logging.Filter):
    def filter(self, record):
        return "internal.py" not in record.getMessage()


formatter_options = dict(fmt=formatter_string, datefmt=coloredlogs.DEFAULT_DATE_FORMAT)
console_formatter_obj = coloredlogs.ColoredFormatter(**formatter_options)
file_formatter_obj = coloredlogs.BasicFormatter(**formatter_options)
fileHandler = logging.FileHandler(f"{os.path.dirname(os.path.abspath(__file__))}/../../log/app.log")
fileHandler.setFormatter(file_formatter_obj)
# consoleHandler = logging.StreamHandler()
# consoleHandler.setFormatter(console_formatter_obj)


def getLogger(name):
    # logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(name)
    logger.addHandler(fileHandler)
    # logger.addHandler(consoleHandler)
    # logger.setLevel(logging.WARNING)
    logger.addFilter(FileHandlerFilter())
    return logger


def setLogger(_logger, name=None):
    if name == 'celery':
        new_fileHandler = logging.FileHandler(f"{os.path.dirname(os.path.abspath(__file__))}/../../log/celery_task.log")
        new_fileHandler.setFormatter(file_formatter_obj)
        _logger.addHandler(new_fileHandler)
    else:
        _logger.addHandler(fileHandler)
    _logger.addFilter(FileHandlerFilter())
    return _logger
