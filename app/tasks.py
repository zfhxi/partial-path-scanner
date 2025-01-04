from celery import shared_task
from app.utils import getLogger, folder_scan, manual_scan
from app.extensions import redis_db, storage_client, fc_handler


logger = getLogger(__name__)


# shared_task usage can refer to https://flask.palletsprojects.com/en/stable/patterns/celery/
@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def mtime_updating(self, folder, blacklist, servers_cfg, fetch_mtime_only, fetch_all_mode):
    try:
        folder_scan(
            folder,
            blacklist,
            servers_cfg,
            storage_client=storage_client,
            db=redis_db,
            fetch_mtime_only=fetch_mtime_only,
            fetch_all_mode=fetch_all_mode,
            this_logger=logger,
        )
        logger.warning(f"目录[{folder}]的mtime更新任务完成!")
    except Exception as e:
        raise Exception(f"目录[{folder}]的mtime更新任务失败! 错误信息: {e}")


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def mtime_clearing(self, folder):
    try:
        for k in redis_db.scan_iter(match=f"{folder}*"):
            redis_db.delete(k)
        logger.warning(f"目录[{folder}]的mtime清空任务完成!")
    except Exception as e:
        raise Exception(f"目录[{folder}]的mtime清空任务失败! 错误信息: {e}")


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def manual_scan_bg(self, folder, servers_cfg):
    rval, message = manual_scan(folder, servers_cfg, storage_client, redis_db)
    if rval:
        logger.info(f"手动扫描路径[{folder}]完成!")
    else:
        raise Exception(f"手动扫描路径[{folder}]失败! 错误信息: {message}")


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def async_filechange_to_other_device(self, upstream_url, payload):
    rmsg = fc_handler.sync_filechange_to_other_device(upstream_url, payload)
    if rmsg:
        logger.warning(rmsg)
