FROM python:3.12-alpine

ENV LANG="C.UTF-8" \
    TZ="Asia/Shanghai" \
    CONFIG_FILE="/config/config.yaml" \
    CRONTAB="*/10 * * * *" \
    DB_FILE="/config/dbkv.sqlite"

COPY ./requirements.txt requirements.txt
RUN apk add logrotate \
    && apk add gcc python3-dev musl-dev linux-headers \
    && pip install --no-cache-dir -r requirements.txt\
    && mkdir /config \
    && mkdir /app

COPY template/logrotate.conf /etc/logrotate.d/partialpathscanner
COPY template/config.yaml /template/config.yaml
COPY entrypoint /entrypoint
COPY app/*.py /app/
WORKDIR /app
RUN chmod +x /entrypoint \
    && chmod 644 /etc/logrotate.d/partialpathscanner

ENTRYPOINT ["/bin/sh","/entrypoint"]