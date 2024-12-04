from gevent import pywsgi
from app import app, FLASK_DEBUG
from app.utils import getLogger

logger = getLogger(__name__)
if __name__ == '__main__':
    logger.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    logger.warning("程序启动中......")
    logger.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
    if FLASK_DEBUG:
        app.run(host=app.config['FLASK_HOST'], port=app.config['FLASK_PORT'])
    else:
        server = pywsgi.WSGIServer((app.config['FLASK_HOST'], app.config['FLASK_PORT']), app)
        server.serve_forever()
