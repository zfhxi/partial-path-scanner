# partial-path-scanner

利用watchdog监控目录变化，然后进行plex/emby media server的局部扫描。  
Utilize watchdog to monitor directory changes, then carry out partial scans for plex/emby media server.

## Disclaimer

* 本项目处于探索中，不建议小白直接使用。若出现资源损坏现象，概不负责！  
This project is in the exploration stage, not recommended for beginners to use directly. We are not responsible for any resource damage that may occur.


## Usage

### Environment
**Setting 1**

* QNAP x86_64
* Plex Media Server with docker
* clouddrive2添加阿里云盘/115网盘，挂载到本地目录`/share/SSD1T/03cd2/{aliyun,115}`，文件夹缓存期40s。  
Add aliyundrive or 115 network disk to clouddrive2, and mount them to the local directories `/share/SSD1T/03cd2/{aliyun,115}`, with a folder cache period of 40s.

**Setting 2**
* Unraid 7.0.0-beta.1
* EmbyServer from app center
* clouddrive2添加阿里云盘/115网盘，挂载到本地目录`/mnt/user/CloudDrive/{aliyun,115}`，文件夹缓存期40s。  
Add aliyundrive or 115 network disk to clouddrive2, and mount them to the local directories `/mnt/user/CloudDrive/{aliyun,115}`, with a folder cache period of 40s.


### Deploy
`docker-compose.yaml`:
```yaml
services:
  partial-path-scanner:
    image: zfhxi/partialpathscanner:latest
    container_name: partial-path-scanner
    network_mode: host
    restart: unless-stopped
    environment:
      - POOL_SIZE=4 # Number of processes for multi-process monitoring
    volumes:
      - ./config:/config
      - /mnt/user/CloudDrive:/mnt/user/CloudDrive:rslave # mapping the path mounted the network drive.
```
* 部署后，修改`./config/config.yaml`中的plex/emby信息和需要监控的目录后，再重启。  
After deployment, modify the plex/emby information and the directories to be monitored in `./config/config.yaml`, then restart.

## TODO

- [x] 为emby media server实现该项目的功能?
- [ ] 为jellyfin media server实现该项目的功能?
- [ ] plex相关api无法刷新单个文件，只能刷新目录。若目录A中多个文件同时变更，会导致多次刷新，是否可以优化？