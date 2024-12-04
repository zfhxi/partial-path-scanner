from app import app

bind = f"{app.config['FLASK_HOST']}:{app.config['FLASK_PORT']}"
workers = 1
threads = 4
