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
* clouddrive2添加阿里云盘，挂载到本地目录`/share/SSD1T/03cd2/aliyun`，文件夹缓存期40s。  
Add aliyundrive to clouddrive2, and mount them to the local directories `/share/SSD1T/03cd2/aliyun`, with a folder cache period of 40s.
* 仅监测目录`/share/SSD1T/03cd2/aliyun/{电影,电视}`。  
Only monitor the directories `/share/SSD1T/03cd2/aliyun/{电影,电视}`.

**Setting 2**
* Unraid 7.0.0-beta.1
* EmbyServer from app center
* clouddrive2添加阿里云盘，挂载到本地目录`/mnt/user/CloudDrive/aliyundrive`，文件夹缓存期40s。  
Add aliyundrive to clouddrive2, and mount them to the local directories `/mnt/user/CloudDrive/aliyundrive`, with a folder cache period of 40s.
* 在Setting 1环境中的QNAP设备上监测目录`/share/SSD1T/03cd2/aliyun/{电影,电视}`，扫描时，映射到`/mnt/user/CloudDrive/aliyundrive/{电影,电视}`。  
Monitor the directories `/share/SSD1T/03cd2/aliyun/{电影,电视}` on the QNAP device in the Setting 1 environment, and when scanning, map to `/mnt/user/CloudDrive/aliyundrive/{Movies,TV}`.



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
      - NUM_WORKERS=2 # Number of workers for multi-threaded scanning
    volumes:
      - ./config:/config
      - /mnt/user/CloudDrive:/mnt/user/CloudDrive:rslave # mapping the path mounted the network drive.
```
* 部署后，修改`./config/config.yaml`中的plex/emby信息和需要监控的目录后，再重启。  
After deployment, modify the plex/emby information and the directories to be monitored in `./config/config.yaml`, then restart.

## TODO

- [x] 为emby media server实现该项目的功能。
- [ ] ~~为jellyfin media server实现该项目的功能。~~（已弃用jellyfin media serve，放弃计划）
- [x] plex相关api无法刷新单个文件，只能刷新变更文件的父目录A。若目录A中多个文件同时变更，会导致多次刷新，待修复。
- [ ] ~~当目录树较大（文件较多时），监测文件变化将占用极高资源，待优化。~~（难度过高，已放弃）