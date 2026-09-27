# weread-docker

把微信读书书架上的书，通过纯 HTTP 协议下载为 EPUB，本地自托管。

纯 HTTP 协议实现，ARM64 Docker 部署，可在飞牛 NAS 等设备上运行。

## 文档

| 文件 | 内容 |
|---|---|
| README.md | 用户文档：安装、使用、配置 |
| DEVELOPMENT.md | 开发规范 + 测试标准 + 微信读书协议 |
| DEPLOY.md | 部署流程（ARM 构建推送 GHCR） |
| HANDOFF.md | 当前进度、待办（供 AI 新会话交接） |

## 特性

- 扫码登录，无需浏览器
- 纯 HTTP，无 Puppeteer/Canvas Hook，内存 < 100MB
- 支持文本型和 EPUB 型章节，自动合并分片
- 打包为标准 EPUB 3，可直接导入 Calibre-Web / KOReader
- 增量下载，已下载自动跳过
- 支持 ARM64，官方 python:3.12-slim 基础镜像
- OPDS 1.2 目录服务，阅读器客户端（KOReader 等）可直接拉书

## 快速开始

### 本地开发

```bash
git clone https://github.com/jiangjun-wangu/weread-docker.git
cd weread-docker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 扫码登录
python3 -m app.main login

# 列出书架
python3 -m app.main shelf

# 下载一本
python3 -m app.main download <bookId>

# 全量同步
python3 -m app.main sync
```

### Docker 部署

```bash
mkdir -p config output
docker compose build

# 扫码登录
docker compose run --rm weread-downloader login

# 同步书架
docker compose run --rm weread-downloader sync
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| CONFIG_DIR | /app/config | 配置目录（session.json 等） |
| OUTPUT_DIR | /app/output | EPUB 输出目录 |
| DOWNLOAD_INTERVAL | 3 | 请求间隔（秒） |
| MAX_PER_MONTH | 100 | 每月下载上限 |
| AUTO_SYNC | false | 启动时自动同步 |
| PORT | 8765 | Web UI 端口（待实现） |
| LOG_LEVEL | info | 日志级别 |

## CLI 命令

| 命令 | 说明 |
|---|---|
| login | 扫码登录，保存 session |
| shelf | 列出书架 |
| download <bookId> | 下载指定书籍 |
| sync | 全量同步书架，跳过已下载 |

## 输出结构

```
output/
├── 活着 - 余华.epub
├── 三体全集（全三册） - 刘慈欣.epub
└── ...

config/
├── session.json    登录状态
├── downloaded.json 已下载清单
├── rate.json       每月下载计数
└── settings.json   用户配置
```

## 与 Calibre-Web 集成

将 OUTPUT_DIR 挂载到 Calibre-Web 的书库目录，或使用 auto-import 容器自动导入：

```yaml
volumes:
  - /vol1/1000/书籍中心/微信读书-书架:/app/output
```

## 技术说明

- 纯 HTTP 协议实现，无浏览器依赖
- 分片解码顺序：copyShardBody → reverseSwaps → Base64UrlDecoder
- 请求体签名：encodeId + signQuery
- EPUB 3.0，含 nav.xhtml + content.opf + 各章 XHTML

## 免责声明

本项目仅供个人学习研究使用，下载内容请勿传播。
使用本工具产生的一切后果由使用者自行承担。

## License

MIT

## 与 Calibre-Web 联动

docker-compose.calibre.yml 把三个服务编排在一起：

```
weread-downloader  ──EPUB──▶  /vol1/1000/书籍中心/微信读书-书架/
                                      │
                                      ▼
                              auto-import 每 15 秒扫描
                                      │  calibredb add
                                      ▼
                              ./calibre/books/  书库
                                      │
                                      ▼
                              calibre-web :9883 展示
```

### 启动

```bash
mkdir -p calibre/config calibre/books calibre/state calibre/scripts
docker compose -f docker-compose.calibre.yml up -d
```

### 端口

- 8765：下载工具 Web UI
- 9883：Calibre-Web

### 目录说明

- ./config            下载工具配置
- ./calibre/config    Calibre-Web 配置
- ./calibre/books     Calibre 书库
- ./calibre/state     auto-import 已导入清单
- ./calibre/scripts/auto-import.sh  导入脚本
- /vol1/1000/书籍中心/微信读书-书架  下载输出，也是 auto-import 输入目录
