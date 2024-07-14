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
* clouddrive2添加阿里云盘/115网盘，挂载到本地目录`/share/SSD1T/03cd2/{aliyun,115}`

**测试环境2**
* Unraid 7.0.0-beta.1
* app中心部署官方的EmbyServer
* clouddrive2添加阿里云盘/115网盘，挂载到本地目录`/mnt/user/CloudDrive/{aliyun,115}`


**docker-compose部署**

```yaml
services:
  partial-path-scanner:
    image: zfhxi/partialpathscanner:latest
    container_name: partial-path-scanner
    network_mode: host
    restart: unless-stopped
    volumes:
      - ./config:/config
      # 以下目录挂载的写法，要和plex容器一致！（如果你的plex不是套件的话）
      - /share/SSD1T/03cd2:/share/SSD1T/03cd2:rslave # cd2挂载到本地
      - /share/HDD1:/share/HDD1 # 本地盘1
      - /share/HDD2:/share/HDD2 # 本地盘2
```
* 部署后，修改`./config/config.yaml`中的plex/emby信息和需要监控的目录后，再重启。

## TODO

- [x] 为emby media server实现该项目的功能?
- [ ] 找更多bug并修复；
- [ ] 为jellyfin media server实现该项目的功能?
- [ ] 调查使用watchdog轮询目录变更，与整库刷新对文件系统的访问压力是否等价？（目前使用该项目可能只是个定心丸）