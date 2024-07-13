import os
from getpass import getuser
from crontab import CronTab, CronSlices


def list_jobs(_cron):
    for j in _cron:
        print(j)


if __name__ == "__main__":
    _CRONTAB = os.getenv("CRONTAB", "* * * * *").strip('"')
    val_bool = CronSlices.is_valid(_CRONTAB)
    if not val_bool:
        raise ValueError(f"{_CRONTAB} is invalid!")
    else:
        print(f"crontab: {_CRONTAB}")

    with CronTab(user=getuser()) as cron:
        command_str = "cd /app && python -u main.py >> /app/output.log 2>&1"
        remove_number = cron.remove_all(command=command_str)
        if remove_number > 0:
            print(f"WARN: {remove_number} jobs has been removed!")
        job = cron.new(command=command_str)
        job.setall(_CRONTAB)
