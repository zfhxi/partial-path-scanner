# mtimebasedscan4plex

## 注意

* 本项目处于探索中，不建议小白直接使用。若出现资源损坏现象，概不负责！


## 使用场景

* 定期监测本地目录的修改时间，并触发plex/emby的局部扫描

> 注：
> - 使用115网盘时，/A/B/目录下新增资源C.mkv，会使B的mtime产生变化，A的mtime不变，比较好处理。
> - 使用阿里云盘时，某一目录/A/B/新增了资源C.mkv，不影响B的mtime，该如何高效判定呢？


## 部署
**个人环境简要说明**

**测试环境1**

* QNAP x86_64系统
* docker部署plex media server
* clouddrive2添加阿里云盘/115网盘，挂载到本地目录`/share/SSD1T/03cd2/{aliyun,115}`

**测试环境2**
* Unraid 7.0.0-beta.1
* app中心部署官方的EmbyServer
* clouddrive2添加阿里云盘/115网盘，挂载到本地目录`/mnt/user/CloudDrive/{aliyun,115}`


**docker-compose部署**

```yaml
services:
  mtimebasedscan4plex:
    image: zfhxi/mtimebasedscan4plex:latest
    container_name: mtimebasedscan4plex
    network_mode: host
    environment:
      - CRONTAB="*/10 * * * *"
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

## TODO

- [ ] 是否考虑更高效的键值对数据库（目前方案为[zackees/keyvalue_sqlite](https://github.com/zackees/keyvalue_sqlite)）；
- [x] 为emby media server实现该项目的功能?
- [ ] 找更多bug并修复；
- [ ] 为jellyfin media server实现该项目的功能?