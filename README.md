# partial-path-scanner

利用watchdog监控目录变化，然后进行plex/emby media server的局部扫描。

## 注意

* 本项目处于探索中，不建议小白直接使用。若出现资源损坏现象，概不负责！


## 使用场景

* 定期监测本地目录的修改时间，并触发plex/emby的局部扫描


## 部署
**个人环境简要说明**

**测试环境1**

* QNAP x86_64系统
* docker部署plex media server
* clouddrive2添加阿里云盘/115网盘，挂载到本地目录`/share/SSD1T/03cd2/{aliyun,115}`，文件夹缓存期40s。

**测试环境2**
* Unraid 7.0.0-beta.1
* app中心部署官方的EmbyServer
* clouddrive2添加阿里云盘/115网盘，挂载到本地目录`/mnt/user/CloudDrive/{aliyun,115}`，文件夹缓存期40s。


**docker-compose部署**

```yaml
services:
  partial-path-scanner:
    image: zfhxi/partialpathscanner:latest
    container_name: partial-path-scanner
    network_mode: host
    restart: unless-stopped
    environment:
      - POOL_SIZE=4 # 多进程监测的进程数
    volumes:
      - ./config:/config
      # 以下目录的挂载，尽量和plex保持一致!
      - /share/SSD1T/03cd2:/share/SSD1T/03cd2:rslave # cd2挂载到本地
      - /share/HDD1:/share/HDD1 # 本地盘1
      - /share/HDD2:/share/HDD2 # 本地盘2
```
* 部署后，修改`./config/config.yaml`中的plex/emby信息和需要监控的目录后，再重启。

## TODO

- [x] 为emby media server实现该项目的功能?
- [ ] 为jellyfin media server实现该项目的功能?
- [ ] plex相关api无法刷新单个文件，只能刷新目录。若目录A中多个文件同时变更，会导致多次刷新，是否可以优化？