from celery import shared_task
from app.utils import getLogger, folder_scan
from app.extensions import redis_db, cd2


logger = getLogger(__name__)


# shared_task usage can refer to https://flask.palletsprojects.com/en/stable/patterns/celery/
@shared_task(ignore_result=False, auto_retry=[Exception], max_retries=3)
def mtime_updating(folder, blacklist, servers_cfg, fetch_mtime_only, fetch_all_mode):
    try:
        folder_scan(
            folder,
            blacklist,
            servers_cfg,
            fs=cd2.fs,
            db=redis_db,
            fetch_mtime_only=fetch_mtime_only,
            fetch_all_mode=fetch_all_mode,
            this_logger=logger,
        )
        logger.warning(f"目录[{folder}]的mtime更新任务完成!")
    except Exception as e:
        logger.error(f"目录[{folder}]的mtime更新任务失败! 错误信息: {e}")


@shared_task(ignore_result=False)
def mtime_clearing(folder):
    try:
        for k in redis_db.scan_iter(match=f"{folder}*"):
            redis_db.delete(k)
        logger.warning(f"目录[{folder}]的mtime清空任务完成!")
    except Exception as e:
        logger.error(f"目录[{folder}]的mtime清空任务失败! 错误信息: {e}")
