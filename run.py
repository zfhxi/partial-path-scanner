from app import flask_app, FLASK_DEBUG
from app.utils import getLogger
from flask_cors import CORS

logger = getLogger(__name__)

if __name__ == '__main__' or 'run':
    CORS(flask_app)
    logger.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    logger.warning("程序启动中......")
    logger.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
    if FLASK_DEBUG:
        flask_app.run(host=flask_app.config['FLASK_HOST'], port=flask_app.config['FLASK_PORT'])
    else:
        from gevent import pywsgi

        server = pywsgi.WSGIServer((flask_app.config['FLASK_HOST'], flask_app.config['FLASK_PORT']), flask_app)
        server.serve_forever()
