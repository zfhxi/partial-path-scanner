# partial-path-scanner

利用[python-clouddrive-client](https://github.com/ChenyangGao/web-mount-packs/tree/main/python-clouddrive-client)提供的clouddrive2 api配合目录的mtime属性监控目录变化，然后进行plex/emby media server的局部扫描（即定期遍历所有目录，检测目录的mtime属性是否发生变化，若发生变化，则对该目录下的媒体路径进行扫描）。  
Using the clouddrive2 api provided by [python-clouddrive-client](https://github.com/ChenyangGao/web-mount-packs/tree/main/python-clouddrive-client) in conjunction with the mtime attribute of the directory to monitor directory changes, and then perform a partial scan of the media paths in plex/emby media server (i.e., periodically traversing all directories, detecting if the mtime attribute of a directory has changed, and scanning the media paths in that directory if it has changed).

## Disclaimer

* 本项目处于探索中，不建议小白直接使用。
This project is in the exploration stage, not recommended for beginners to use directly.


## Usage

### Environment
**Setting 1**
* QNAP x86_64
* Plex Media Server with docker
* clouddrive2添加115网盘，挂载到本地目录`/share/SSD1T/03cd2/115`，文件夹缓存期40s。  
Add 115 netdisk to clouddrive2, and mount it to the path of local filesystem `/share/SSD1T/03cd2/115`, with a folder cache period of 40s.
* 仅监测目录`/share/SSD1T/03cd2/115/{电影,电视}`。  
Only monitor the directories `/share/SSD1T/03cd2/115/{电影,电视}`.

**Setting 2**
* Unraid 7.0.0-beta.2
* EmbyServer from app center
* clouddrive2添加115网盘，挂载到本地目录`/mnt/user/CloudDrive/115`，文件夹缓存期40s。  
Add 115 netdisk to clouddrive2, and mount it to the path of local filesystem `/mnt/user/CloudDrive/115`, with a folder cache period of 40s.
* 在Setting 1环境中的QNAP设备上监测cd2目录`/115/Public/{电影,电视}`，扫描时，映射到`/mnt/user/CloudDrive/115/{电影,电视}`。  
Monitor the directories `/115/Public/{电影,电视}` on the QNAP device in the Setting 1 environment, and when scanning, map to `/mnt/user/CloudDrive/115/{电影,电视}`.



### Deploy

先建立`xxxx/config/config.yaml`文件，内容如下：
```yaml
cd2:
  host: http://192.168.xxx.xxx:19798
  user: your@mail.com
  password: your-password
servers: ['plex','emby'] # 可以只保留'plex'或'emby'
plex:
  host: http://192.168.xxx.xxxx:32400
  token: your-plex-token
  path_mapping: # cd2中的路径映射到plex中
    enable: true
    rules:
      - from: /115/Public
        to: /share/SSD1T/03cd2/115
emby:
  host: https://your.emby.com
  api_key: your-emby-api-key
  path_mapping: # cd2中的路径映射到emby中
    enable: true
    rules:
      - from: /115/Public
        to: /mnt/user/CloudDrive/115
MONITOR_FOLDER:
  /115/Public/电视:
    blacklist: ['/115/Public/电视/纪录片'] # 黑名单，不会被扫描
    overwrite_db: false #构建数据库时，对数据库中已存在的时间采用覆盖模式（当该程序很久未启动时，且plex/emby media server早已扫描过网盘全部内容，数据库中的时间戳已经过时了，需要强制更新）
  /115/Public/电影:
    blacklist: ['/115/Public/电影/日本电影'] # 黑名单，不会被扫描
    overwrite_db: false
```
再基于如下`docker-compose.yaml`构建docker容器:
```yaml
services:
  partial-path-scanner:
    image: zfhxi/partialpathscanner:dev
    container_name: partial-path-scanner
    network_mode: host
    restart: unless-stopped
    environment:
      - CRONTAB="*/30 * * * *" # if the storage of your netdisk is large, you can set it to 0 */1 * * * or 0 */2 * * *.
      #- STARTUP_BUILD_DB=true # if you want to build the database when the container starts, keep it to the default value, otherwise set it to false.
    volumes:
      - xxx/config:/config
```
或者直接使用`docker run`命令:
```bash
docker run --name=partial-path-scanner \
        --env='CRONTAB="*/30 * * * *"' \
        --volume=xxx/config:/config:rw \
        --network=host \
        --restart=unless-stopped \
        zfhxi/partialpathscanner:dev
```

每次更改`config.yaml`文件后，需要重启容器。

## TODO

- [ ] find more bugs.
- [x] ~~阿里云盘目录的mtime不会随子文件新增而变化，需要额外的逻辑处理。~~（never in plan）