# partial-path-scanner

利用[python-clouddrive-client](https://github.com/ChenyangGao/web-mount-packs/tree/main/python-clouddrive-client)提供的clouddrive2 api配合目录的mtime属性监控目录变化，然后进行plex/emby media server的局部扫描（即定期遍历所有目录，检测目录的mtime属性是否发生变化，若发生变化，则对该目录下的媒体路径进行扫描）。  

## 免责声明

* 本项目处于探索中，不建议小白直接使用。  


## 用法

### 环境
**测试环境 1**
* QNAP x86_64
* Plex Media Server with docker
* clouddrive2添加115网盘，挂载到本地目录`/share/SSD1T/03cd2/115`，文件夹缓存期40s。  
* 仅监测目录`/share/SSD1T/03cd2/115/{电影,电视}`。  

**测试环境 2**
* Unraid 7.0.0-beta.2
* EmbyServer from app center
* clouddrive2添加115网盘，挂载到本地目录`/mnt/user/CloudDrive/115`，文件夹缓存期40s。  
* 在Setting 1环境中的QNAP设备上监测cd2目录`/115/{电影,电视}`，扫描时，映射到`/mnt/user/CloudDrive/115/{电影,电视}`。  



### 部署

先建立`xxxx/partialpathscanner/config/config.yaml`文件，内容如下：
```yaml
cd2:
  host: http://192.168.xxx.xxx:19798
  user: your@mail.com
  password: your-password
servers: ['plex','emby'] # 可以只保留'plex'或'emby'
plex:
  host: http://192.168.xxx.xxxx:32400
  token: your-plex-token
  isfile_based_scanning: false # 基于局部文件的扫描，而不是扫描变更文件的父目录；否则扫描变更文件的父目录。如果变更的是目录，则扫描变更目录。
  path_mapping: # cd2中的路径映射到plex容器中的路径
    enable: true
    rules:
      - from: /115
        to: /share/SSD1T/03cd2/115
emby:
  host: https://your.emby.com
  api_key: your-emby-api-key
  isfile_based_scanning: true
  path_mapping: # cd2中的路径映射到emby容器中的路径
    enable: true
    rules:
      - from: /115
        to: /mnt/user/CloudDrive/115
MONITOR_FOLDER: # 监控目录
  /115/Public/电视/国产动漫剧/shen墓 (2022)/Season 2:
    schedule_interval: 1h
    schedule_random_offset: 0.1
  /115/Public/电视/国产动漫剧/完meishi界 (2021):
    schedule_interval: 1h
    schedule_random_offset: 0.1
  /115/Public/电视/国产动漫剧/刺xxx七 (2018)/Season 5:
    schedule_interval: 1h
    schedule_random_offset: 0.1
  /115/Public/电视/国产动漫剧/x来 (2024):
    schedule_interval: 1h
    schedule_random_offset: 0.1
  /115/Public/电视:
    schedule_interval: 1d
    #blacklist: ['/115/Public/电视/综艺','/115/Public/电视/纪录片']
  /115/Public/电影:
    schedule_interval: 1d
```
可选参数的说明：
- `blacklist`：黑名单目录列表，不会被遍历。
- `schedule_interval`：遍历扫描间隔，默认1h（由DEFAULT_INTERVAL确定），可更改为xm（分钟）、xh（小时）、xd（天），x为正整数。
- `schedule_random_offset`：建议设置。随机扫描时间百分偏移，默认不偏移。若设置为0.1，则下一次扫描发生在`schedule_interval`~`schedule_interval*1.1`后。
- `overwrite_db`: 一般不需要设置。构建数据库时，对数据库中已存在的时间采用覆盖模式（当该程序很久未启动时，且plex/emby media server早已扫描过网盘全部内容，数据库中的时间戳已经过时了，需要强制更新）

再基于如下`docker-compose.yaml`构建docker容器:
```yaml
services:
  partial-path-scanner:
    image: zfhxi/partialpathscanner:dev
    container_name: partial-path-scanner
    network_mode: host
    restart: unless-stopped
    environment:
      - DEFAULT_INTERVAL="1h"
    volumes:
      - xxx/config:/config
```
或者直接使用`docker run`命令:
```bash
docker run --name=partial-path-scanner \
        --env='DEFAULT_INTERVAL="1h"' \
        --volume=xxx/config:/config:rw \
        --network=host \
        --restart=unless-stopped \
        zfhxi/partialpathscanner:dev
```

每次更改`config.yaml`文件后，需要重启容器。

运行逻辑：  
1. 容器启动时，构建数据库，将监控目录的所有子目录的mtime属性存入数据库。（所以使用该项目前，请保证已有的影视文件都已经入库了，否则未入库的文件不会被本项目扫描，因为其mtime在启动时被存入数据库）
2. 定时任务每间隔特定时间来遍历监控目录，检查该目录及其子目录的mtime属性是否发生变化，若发生变化，则对该目录下的媒体路径进行扫描。  
3. 扫描时，根据配置文件中的`path_mapping`规则，将clouddrive2中的路径映射到plex/emby media server的路径。  

## 手动扫描特定目录

（在容器正常创建并运行后）如果刚转存了某个剧的第二季，希望立马扫描该目录，可以执行：
```bash
docker exec -it partial-path-scanner python main.py --scan-path="/115/电视/国产动漫剧/xxxx (2022)/Season 2"
```

## 局限性

**最近115风控厉害，建议cd2中115的maxQueriesPerSecond参数调小（如0.9），尽管这样会导致遍历目录树时间加长，但可以缓解风控。**

## TODO

- [ ] find more bugs.
- [x] ~~阿里云盘目录的mtime不会随子文件新增而变化，需要额外的逻辑处理。~~（never in plan）
- [x] plex media server 1.41.2.9200版本似乎不支持xxx.mkv这种单个文件入库了，需要扫描父目录。