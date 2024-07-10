# mtimebasedscan4plex

## 注意

* 本项目处于探索中，不建议小白直接使用。若出现资源损坏现象，概不负责！


## 使用场景

* 定期监测本地目录的修改时间，并触发plex的局部扫描

## 部署

docker-compose部署：
```yaml
services:
  mtimebasedscan4plex:
    image: zfhxi/mtimebasedscan4plex:latest
    container_name: mtimebasedscan4plex
    network_mode: host
    environment:
      - CRONTAB="*/10 * * * *"
      - POOL_SIZE=1 # 可设置为多进程
    restart: unless-stopped
    volumes:
      - ./config:/config
      # 以下目录挂载的写法，要和plex容器一致！（如果你的plex不是套件的话）
      - /share/SSD1T/03cd2:/share/SSD1T/03cd2:rslave # cd2挂载到本地
      - /share/HDD1:/share/HDD1 # 本地盘1
      - /share/HDD2:/share/HDD2 # 本地盘2
```
* 根据情况修改`- CRONTAB="*/10 * * * *"`，通过crontab表达式来定期执行监测文件。
* 部署后，修改`./config/config.yaml`中的plex信息和需要监控的目录后，再重启。

