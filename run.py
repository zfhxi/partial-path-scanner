from gevent import pywsgi
from app import app, FLASK_DEBUG

if __name__ == '__main__':
    if FLASK_DEBUG:
        app.run(host=app.config['FLASK_HOST'], port=app.config['FLASK_PORT'])
    else:
        server = pywsgi.WSGIServer((app.config['FLASK_HOST'], app.config['FLASK_PORT']), app)
        server.serve_forever()
