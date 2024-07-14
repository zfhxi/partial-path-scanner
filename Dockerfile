# FROM python:3.12-slim
FROM python:3.12-alpine

# 环境变量
ENV LANG="C.UTF-8" \
    TZ="Asia/Shanghai" \
    CONFIG_FILE="/config/config.yaml"

COPY ./requirements.txt requirements.txt
RUN apk add logrotate \
    && pip install --upgrade pip\
    && pip install --no-cache-dir -r requirements.txt\
    && mkdir /config \
    && mkdir /app

COPY template/logrotate.conf /etc/logrotate.d/mtimebasedscan4plex
COPY template/config.yaml /template/config.yaml
COPY entrypoint /entrypoint
COPY app/*.py /app/
WORKDIR /app
RUN chmod +x /entrypoint \
    && chmod 644 /etc/logrotate.d/mtimebasedscan4plex

ENTRYPOINT ["/bin/sh","/entrypoint"]