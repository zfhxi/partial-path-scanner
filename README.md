# partial-path-scanner

利用[python-clouddrive-client](https://github.com/ChenyangGao/web-mount-packs/tree/main/python-clouddrive-client)提供的clouddrive2 api配合目录的mtime属性监控目录变化，然后进行plex/emby media server的局部扫描（即定期遍历所有目录，检测目录的mtime属性是否发生变化，若发生变化，则对该目录下的媒体路径进行扫描）。  

![监控列表](./img/monitor.png)

![目录浏览](./img/files.png)

## 免责声明

* 本项目处于开发中，不建议小白直接使用。  

## 依赖

* Python
* Flask
* Bootstrap
* python-clouddrive-client
* ...

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

先拷贝项目中的`template/config.yaml`到`你的compose项目目录/config/config.yaml`，并按需修改（WEBUI的启动端口2024，默认登录用户名admin，密码admin等）。

再基于如下`docker-compose.yaml`构建docker容器:
```yaml
services:
  partial-path-scanner:
    image: zfhxi/partialpathscanner:beta
    container_name: pp-scanner
    network_mode: host
    restart: unless-stopped
    volumes:
      - ./config:/app/config
      - ./log:/app/log
    depends_on:
      - pps-redis
  pps-redis:
    image: redis:7.4.1
    container_name: pps-redis
    restart: always
    network_mode: bridge
    environment:
      - REDIS_ARGS="--user default --requirepass helloworld --appendonly yes"
    ports:
      - 6379:6379
    volumes:
      - ./redis_data:/data
```

打开`http://你的ip:2024`即可访问web ui（推荐PC端访问，因为没有做移动端UI适配）。

每次更改`config.yaml`文件后，需要重启容器。

运行逻辑：  
1. 将监控目录的所有子目录的mtime属性存入数据库。
2. 定时任务每间隔特定时间来遍历监控目录，检查该目录及其子目录的mtime属性是否发生变化，若发生变化，则对该目录下的媒体路径进行扫描。  
3. 扫描时，根据配置文件中的`path_mapping`规则，将clouddrive2中的路径映射到plex/emby media server的路径。  

## 局限性

**最近115风控厉害，建议cd2中115的maxQueriesPerSecond参数调小（如0.9），尽管这样会导致遍历目录树时间加长，但可以缓解风控。**

## TODO

- [ ] find more bugs.
- [ ] 生产模式的多线程环境下，CloudDriveFileSystem第一次调用类方法会抛出`OSError: Socket operation on non-socket (88)`；开发模式下不抛出异常。需要更优雅的解决方案。
- [x] ~~阿里云盘目录的mtime不会随子文件新增而变化，需要额外的逻辑处理。~~（移除计划：开发者弃用阿里云盘）
- [x] ~~plex media server 1.41.2.9200版本似乎不支持xxx.mkv这种单个文件入库了，需要扫描父目录。~~（错误的判断，仍保留isfile_based_scanning参数）

## 参考

- [flask-template](https://github.com/HuTa0kj/flask-template)