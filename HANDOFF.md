# weread-docker 交接文档

## 项目概述

微信读书书架纯 HTTP 下载工具，Python 实现，ARM64 Docker 部署，跑在飞牛 NAS。

## 仓库与路径

- GitHub: https://github.com/jiangjun-wangu/weread-docker
- 开发机: JARVIS (x86_64 WSL2)，~/weread-docker
- 目标机: 飞牛 NAS (ARM64)，/vol1/1000/Docker/weread-docker
- 依赖: venv 在 ~/weread-docker/.venv

## 必读文件

- CONVENTIONS.md  开发规范（AI 可读版）
- NOTES.md        协议说明 + 开发日志
- HANDOFF.md      本文件
- README.md       用户文档

## 已完成的模块

- protocol.py   encode_id / sign_query / swap_positions / base64url_decode
                combine_and_decode / url_encode / make_content_body
- config.py     环境变量 + settings.json，路径自适应
- store.py      session / downloaded / rate 读写
- auth.py       扫码登录
- client.py     书架 / 目录 / referer / 分片 / download_chapter
                shelf() 返回带 bookProgress（阅读进度、时长）
- epub.py       EPUB 3.0 打包
- downloader.py 编排、增量跳过、重试、文件名规范（书名 - 作者.epub）
- main.py       CLI（login / shelf / download / sync）
- logger.py     内存日志缓冲 + 订阅
- sorter.py     书架排序筛选 + 中文首字母
- api.py        FastAPI 接口：
                /api/status /api/login/start /api/login/poll /api/logout
                /api/shelf（排序/筛选/分页）
                /api/download /api/download/pause /api/download/resume /api/download/cancel
                /api/download/status /api/download/stream
                /api/records /api/config /api/logs /api/logs/stream
                /api/user（用户信息 + 统计，5 分钟缓存）
- static/       Web UI（index.html / style.css / app.js）
                登录遮罩 + 书架 + 已下载 + 设置 + 日志

## 已实现的功能

- 扫码登录（终端 ASCII 二维码 + 网页二维码）
- 书架：37 本，排序（11 种字段）、筛选（全部/在读/已读完/未读）、分页
- 下载：暂停 / 继续 / 取消，章节级进度条
- 文件名规范：书名 - 作者.epub
- 增量跳过已下载
- 401 自动清 session + 弹遮罩
- 用户信息端点（昵称、头像、统计）

## 待办（下一步）

- [x] 前端展示 /api/user 数据（header 头像 + 昵称）— commit 53c4a62
- [x] 新增「我的」Tab：头像、昵称、uid、统计卡片、最近在读 — commit 53c4a62
- [x] UI 改为微信读书官方风格（主色 #2762D9）— commit c52efc0
- [x] NAS 部署验证 — commit b94033c（arm64 构建 → GHCR → compose pull，二维码/登录/下载正常）
- [x] 接 Calibre-Web auto-import（已验证正常）
- [x] 每月下载限流统计（header 胶囊徽章 + 悬浮提示 + 临界变色）
- [x] auto_sync 定时任务 — commit f577076
- [x] 书架卡片网格 + 搜索 + 传书上传 — commit 4031e50
- [x] 三列表统一分页 + 已下载简介 + 传书排除微信书 — commit 8ad8a59
- [x] 下载队列卡片状态 + 单本取消 + 软/硬删 + 全局 loading — commit 5e95d9e
- [x] on_event → lifespan（消除弃用警告）
- [x] 下载队列持久化 + 重启自动恢复（取消全部清队列）— commit 8c9aae8
- [x] 传书卡片微信匹配（封面+简介）+ 上传结果改 toast — commit 0e2995b
- [x] 书架缓存（TTL 30s）+ 默认「我的」Tab + 登录后预热 — commit 3d43f52
- [x] 刷新书架强制绕缓存（nocache）— commit 2e0932e
- [x] 设置页文案直白化 + 立即检查新书 toast — commit 548f79b
- [x] NAS 重新构建推送（同步 548f79b）

## 当前状态

- 本地 uvicorn 可跑通全流程
- git 最新 commit: 548f79b（设置文案 + 传书匹配 + 书架缓存）
- 已测试：登录、书架、下载、暂停/继续/取消、排序、筛选、分页
- 已测试：/api/user（curl 返回 userVid/nick/avatar/stats/recent，前端 header + 我的 Tab 展示正常）
- NOTES.md 健康检查模式已修正（epub → \.epub，消除 app/epub.py 误报）
- 已测试：/api/sync/now（queued=32，取消后 running:false，无半成品）
- 已测试：auto_sync 调度器启动日志 enabled=False interval=6.0h
- 新增 TESTING.md 测试标准（9 节，含验证方法论），CONVENTIONS 新增 2.6 大块写入防卡
- UI 细化：主色 #2762D9、胶囊按钮、进度条配色、favicon.svg、tag 色调
- 修复：登录成功后书架不自动加载（pollOverlayLogin + pollLogin 两处补 loadShelf）
- CONVENTIONS 1.1 改「提交六步」，第 0 步为用户确认硬门槛
- 新增 docker-compose.dev.yml（开发，build）；docker-compose.yml 改生产（GHCR 镜像）
- CONVENTIONS 新增 5.7 环境隔离铁律：NAS 禁改代码/手改 compose
- requirements.txt 加 Pillow（修容器内二维码生成 500：No module named PIL）
- 新增 DEPLOY.md（ARM 构建推送 GHCR 流程，9 节）
- 构建链路：NAS arm64 原生构建 → push ghcr.io/jiangjun-wangu/weread-docker:latest
- NAS 部署验证通过：二维码/登录/下载正常，git status 干净
- 传书卡片：微信搜索匹配封面 + 简介（/api/match），匹配不到保持 EXT 方块
- 书架缓存：TTL 30s；翻页/排序命中缓存；刷新书架 nocache 绕缓存
- 默认 Tab 改「我的」，登录后 switchTab("me") + 后台预热 loadShelf()
- 下载队列持久化：config/progress/{bookId}.meta.json + _queue.json；重启自动恢复
- 上传结果改 toast（原底部常驻条已删）
- 删 downloader.py 重复类（死代码）

## 关键决策

- Python 3.12 + python:3.12-slim
- httpx 同步客户端
- 后端线程跑下载，SSE 推进度
- session 存 JSON
- 单账号单 session，本地和 NAS 互踢
- 文件名 书名 - 作者.epub
- OUTPUT_DIR 环境变量配置
- 中文首字母用 GB2312 编码映射，不引依赖

## NAS 部署注意

- NAS 上 compose 用 docker-compose.yml（仅下载工具）
- 联动 Calibre 用 docker-compose.calibre.yml
- user: "1000:1001"
- Dockerfile 里 chmod -R a+rX /app/app
- 部署顺序：本地验证 → push → NAS pull → build → up

## 新会话开场提示

继续微信读书 Docker 下载工具开发。
先读 ~/weread-docker/CONVENTIONS.md、NOTES.md、HANDOFF.md。
代码在 ~/weread-docker，git 已关联 GitHub。
遵守 CONVENTIONS.md 的开发规范。
从 HANDOFF.md 的"待办"继续。
先跑健康检查确认环境。
