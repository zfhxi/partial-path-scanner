# FROM python:3.12-slim
FROM python:3.12-alpine

# 环境变量
ENV LANG="C.UTF-8" \
    TZ="Asia/Shanghai" \
    CRONTAB="* * * * *" \
    RELEASE=True \
    CONFIG_FILE="/config/config.yaml" \
    DB_FILE="/config/dbkv.sqlite"

COPY ./requirements.txt requirements.txt
# RUN pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple \
RUN apk add g++ logrotate \
    && apk add gcc python3-dev musl-dev linux-headers \
    && pip install --upgrade pip\
    && pip install --no-cache-dir -r requirements.txt\
    && mkdir /config \
    && mkdir /app

COPY template/logrotate.conf /etc/logrotate.d/mtimebasedscan4plex

COPY template/config.yaml /template/config.yaml
COPY entrypoint /entrypoint
COPY app/*.py /app/
WORKDIR /app
RUN chmod +x /entrypoint

ENTRYPOINT ["/bin/sh","/entrypoint"]