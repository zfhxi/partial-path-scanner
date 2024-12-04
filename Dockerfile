FROM python:3.12-alpine

ENV LANG="C.UTF-8" \
    TZ="Asia/Shanghai" \
    FLASK_DEBUG=0

    #- STARTUP_BUILD_DB=true # if you want to build the database when the container starts, keep it to the default value, otherwise set it to false.
    # && apk add gcc python3-dev musl-dev linux-headers \
WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN apk add logrotate \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && mkdir /app/config \
    && mkdir /app/template \
    && mkdir /app/log

COPY template/logrotate.conf /etc/logrotate.d/partialpathscanner
COPY template/config.yaml /app/template/config.yaml
COPY template/supervisord.conf /etc/supervisord.conf
COPY entrypoint /app/entrypoint
COPY app /app/app
COPY run.py /app/run.py
COPY gunicorn.conf.py /app/gunicorn.conf.py
RUN chmod +x /app/entrypoint \
    && chmod 644 /etc/logrotate.d/partialpathscanner

ENTRYPOINT ["/bin/sh","/app/entrypoint"]