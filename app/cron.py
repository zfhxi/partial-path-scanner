import os, sys
from getpass import getuser
from crontab import CronTab, CronSlices

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import getLogger

logger = getLogger(__name__)


def list_jobs(_cron):
    for j in _cron:
        print(j)


if __name__ == "__main__":
    _CRONTAB = os.getenv('CRONTAB', '*/30 * * * *').replace('"', '').replace("'", "")
    val_bool = CronSlices.is_valid(_CRONTAB)
    if not val_bool:
        raise ValueError(f"{_CRONTAB} is invalid!")
    else:
        logger.info(f"crontab: {_CRONTAB}")

    with CronTab(user=getuser()) as cron:
        command_str = "cd /app && python -u main.py >> /app/output.log 2>&1"
        remove_number = cron.remove_all(command=command_str)
        if remove_number > 0:
            logger.warning(f"{remove_number} jobs has been removed!")
        job = cron.new(command=command_str)
        job.setall(_CRONTAB)
