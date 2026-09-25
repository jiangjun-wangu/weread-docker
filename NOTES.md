# weread-docker 开发说明

微信读书纯 HTTP 下载工具，Python 实现，ARM64 Docker 部署。

## 一、目标环境

- 开发机：JARVIS，x86_64 WSL2，无 docker，用 venv
- 目标机：飞牛 NAS，ARM64，跑 docker
- 流程：本地写代码 → git push → NAS 上 git pull → docker build

## 二、协议核心

- 登录：GET /api/auth/getLoginUid → 二维码 → 轮询 getLoginInfo
- Cookie：wr_vid、wr_skey、wr_rt（HTTP 响应 Set-Cookie 自动收）
- 书架：GET /web/shelf/sync，errcode -2012 表示 session 过期
- 目录：POST /web/book/chapterInfos，body bookIds 数组
- referer：/web/reader/{encodeId(bookId)}k{encodeId(chapterUid)}
- 分片：POST /web/book/chapter/e_0、t_0、t_1、e_1、e_3
- 解码顺序：copyShardBody → reverseSwaps → Base64UrlDecoder
- 类型判定：PK 魔数 → EPUB；bookId 存在 → 文本型；否则 EPUB 型

## 三、已实现模块

- protocol.py：encode_id、sign_query、swap_positions、base64url_decode、combine_and_decode、url_encode、make_content_body
- auth.py：WeReadAuth 类，扫码登录、session 存取、renew
- store.py：session.json、downloaded.json、rate.json 读写
- config.py：环境变量、settings.json
- client.py：书架、目录、referer、分片下载（进行中）

## 四、待办

- client.py：inspect_primary、download_chapter 完整实现
- epub.py：EPUB 打包
- downloader.py：下载引擎、断点续传
- api.py + main.py：FastAPI 接口
- static/：Web UI 单页
- Dockerfile + docker-compose.yml

## 五、开发规范

1. 中文交流，脚本 clear 开头，每轮 1-3 问题
2. 命令直接可跑，先探测再动手
3. 文档写入用 printf 逐行追加，禁 heredoc
4. 提交五步：备份 → add → commit → push → log 确认
5. Python 依赖用 venv，不用 --break-system-packages
6. 含特殊字符的行，用辅助 Python 脚本改写，不用 printf 直接写
7. 命令报错先停，发输出再继续

## 六、失误记录（血泪教训）

1. printf 参数里反斜杠被转义：写正则时 s 被吃，导致语法错误
2. printf 参数里百分号：直接写百分号，不要写双百分号
3. Python 字面百分号要写双百分号：如格式化输出百分号加十六进制
4. grep 双百分号会误判三百分号的行：判断时看上下文
5. 同名函数在 Python 文件里后定义覆盖先定义：可用于修补
6. 容器内外提示符区别：容器内是 root 加哈希，宿主机是用户名

## 七、更新日志

### 2026-09-25（环境固化）

- 新机环境：WSL2 + Ubuntu 26.04.1 LTS（x86_64），默认 Python 3.14，无 python3-venv
- 按 CONVENTIONS 5.1 钉 Python 3.12：deadsnakes PPA 装 python3.12/python3.12-venv/python3.12-dev（3.12.14）
- 避坑：WSL 内不装 docker-ce（get.docker.com TLS 挂）；开发机无需 Docker，构建在 NAS
- 避坑：venv 断链致健康检查 12 模块 FAIL；多次 source 致提示符 ((.venv) ) 嵌套，deactivate+unset VIRTUAL_ENV 清理
- 新增 CONVENTIONS 〇 节「环境自检与依赖安装」（幂等脚本，缺 3.12 自动装）
- 新增 TESTING.md 〇 节「环境自检与依赖安装」，原一~九节顺延
- CONVENTIONS 10.3 / HANDOFF 开场提示改为「先环境自检，再健康检查」
- 健康检查基线：12/12 模块 OK，运行时数据 0，git 干净 201f327

### 2026-09-24（更新）

- 传书卡片微信匹配：/api/match 搜 /web/search/global，取 books[0].bookInfo（封面+简介）
- 书架缓存：_get_shelf_cached TTL 30s；/api/shelf?nocache=1 强制绕缓存
- 默认 Tab 改「我的」；登录后 switchTab("me") + 后台预热 loadShelf()
- 下载队列持久化：config/progress/{book_id}.meta.json + _queue.json；lifespan 检测 + 前端自动恢复
- 取消全部 → 清队列（下次不恢复）；单本 ✕ → 仅移除该本
- 上传结果改 toast；设置页文案直白化
- 删 downloader.py 重复 Downloader 类（死代码）
- 新增 store 函数：save_queue/load_queue/clear_queue/save_progress_meta/load_progress_meta/clear_progress/list_progress

### 2026-09-24（最新）

- 书架卡片网格 + 搜索（书名/作者）+ 传书上传（独立 Tab，落 OUTPUT_DIR）
- 三列表统一分页（书架/已下载/传书）
- 已下载卡片网格 + 书籍简介悬浮（书架下方 / 我的右侧 / 已下载下方）
- 下载队列卡片状态：排队灰标 / 下载中圆环遮罩 / 失败红标 / 已下载蓝标 / 未下载灰标
- 单本 ✕ 取消 + 「下载选中」↔「取消全部」按钮切换 + 本地取消集合防 SSE 覆盖
- 软删（保留文件）/ 硬删（删文件）双按钮
- 全局 loading 遮罩（写操作触发）
- UI 胶囊化：tab 蓝底胶囊、按钮胶囊、卡片角标方角 8px
- 登录后自动加载书架；跨 Tab 刷新书架（传书删/上传/切书架）
- on_event → lifespan（消除 FastAPI 弃用警告）

### 2026-09-24（上）

- compose 环境隔离：docker-compose.yml（生产，GHCR 镜像） + docker-compose.dev.yml（开发，build）
- CONVENTIONS 新增 5.7 环境隔离铁律：NAS 禁改代码/手改 compose
- CONVENTIONS 5.5 部署顺序改为「NAS 构建推送 GHCR → NAS pull」
- requirements.txt 加 Pillow（修容器内二维码生成 500：No module named PIL）
- DEPLOY.md：第六节补精确入口+踩坑，第七章补双 compose 说明

### 2026-09-24（上）

- 新增 DEPLOY.md：ARM 环境 Docker 构建推送 GHCR 完整流程（9 节）
- 构建流程已打通：NAS arm64 原生构建 → 推送 ghcr.io/jiangjun-wangu/weread-docker:v0.1.0-test

### 2026-09-24（下）

- 新增 app/auto_sync.py：后台调度器，回调注入避免循环导入
- config.py：AUTO_SYNC_ENABLED / AUTO_SYNC_INTERVAL_HOURS + 旧字段迁移
- api.py：/api/sync/now、_auto_sync_tick、启动钩子
- 前端设置页：启用自动同步 + 同步间隔（小时）+ 立即同步按钮
- 新增 TESTING.md：健康检查、API 清单、端到端、auto_sync 专项
- CONVENTIONS.md 新增 2.6 大块写入防卡

### 2026-09-24（早期）

- 建项目骨架 ~/weread-docker
- 建 git 仓库，关联 GitHub jiangjun-wangu/weread-docker
- 完成 protocol.py：13 个函数，冒烟测试通过
- 完成 config.py：环境变量 + settings.json
- 完成 store.py：session、downloaded、rate 读写
- 完成 auth.py：WeReadAuth 扫码登录
- 完成 client.py 骨架：shelf、toc、referer、shard、download_chapter
- 建 NOTES.md 开发说明


## 八、部署与数据规范

1. 运行时数据（session.json、downloaded.json、rate.json、settings.json、logs/、progress/、output/*.epub）
   一律不进 git，部署时必须是空的
2. .gitignore 必须包含：
   - config/*   （保留 config/.gitkeep）
   - output/*   （保留 output/.gitkeep）
3. 测试产生的 session.json / output 文件，提交前先删除或确认被忽略
4. 部署到新机器时，config/ 和 output/ 都是空目录，首次必须重新扫码登录
5. 镜像里不预置任何运行时数据，只打包代码

## 九、开发分工与验证标准

### 分工

- 用户：在 VSCode 里粘贴代码、保存文件、执行命令、跑 Docker
- AI：贴出完整代码、给出命令、检查语法/接口/功能、验证结果
- AI 必须主动用 curl 或脚本验证，不能等用户反馈

### 验证标准

每完成一个功能模块，必须跑以下验证，全部通过才算完成：

1. **语法检查**：python3 -c "from app import xxx; print(\"OK\")"
2. **import 检查**：python3 -m app.main --help
3. **接口检查**（curl）：每个 API 端点都要 200 且数据合理
4. **前端检查**：浏览器 F12 无报错，SSE 正常推送
5. **端到端检查**：完整流程跑通（登录→书架→下载→输出文件）

### curl 验证清单

```bash
curl -s http://127.0.0.1:8765/api/status
curl -s http://127.0.0.1:8765/api/shelf
curl -s http://127.0.0.1:8765/api/records
curl -s http://127.0.0.1:8765/api/config
curl -s http://127.0.0.1:8765/api/download/status
curl -s "http://127.0.0.1:8765/api/logs?n=5"
```

### 提交前检查

```bash
git status | grep -E "session|downloaded|rate\.json|\.epub" && echo "有运行时数据" || echo "干净"
tail -3 Dockerfile
```

## 十、一体化健康检查（提交前必跑）

一条命令跑完所有检查，clear 开头，用户复制整行执行：

    clear; cd ~/weread-docker; source .venv/bin/activate
    echo "=== 1. 运行时数据 ==="
    git ls-files | grep -c -E "session|downloaded|rate|\\.epub"
    echo "=== 2. Dockerfile ==="; tail -5 Dockerfile
    echo "=== 3. 模块 import ==="
    for m in protocol config store auth client epub downloader main logger api; do
        python3 -c "from app import $m" && echo "$m OK" || echo "$m FAIL"
    done
    echo "=== 4. static ==="; ls -la app/static/; wc -l app/static/*
    echo "=== 5. git status ==="; git status

判定：1=0，2=CMD api，3=全 OK，4=三文件在，5=只有源码改动

## 十一、会话交接

### 会话使用率到 90% 时

1. AI 主动提醒用户换新会话
2. 生成交接文档 HANDOFF.md 包含：
   - 项目概述
   - 已完成的模块
   - 待办事项
   - 关键决策与约定
   - 下一步该做什么
3. git add + commit + push 交接文档
4. 给用户一段"新会话开场提示"，用户复制给新 AI

### 新会话开场提示模板

    继续微信读书 Docker 下载工具开发。
    先读 ~/weread-docker/NOTES.md 和 ~/weread-docker/HANDOFF.md。
    代码在 ~/weread-docker，git 已关联 GitHub。
    遵守 NOTES.md 的开发规范。
    当前进度在 HANDOFF.md，从"下一步"继续。
    先跑一体化健康检查确认环境。

## 十二、文件修改分工

1. Python / Shell / Dockerfile / docker-compose.yml / requirements.txt：
   用命令（printf 逐行追加）直接改，无需 VSCode
   同名类/函数后定义覆盖先定义，可用于"替换"
2. HTML / CSS / JS：VSCode 里手动粘贴，避免转义地狱
3. 用户只负责 VSCode 粘贴 + 跑命令，其余 AI 做

## 十三、修改前先探测

修改任何文件前，必须先看现状：
1. 列出现有结构：cat 文件 / grep class / wc -l
2. 列出现有 class / 函数 / 导入
3. 确认覆盖度：新方案是否覆盖了所有现有元素
4. 再给出替换/追加命令

禁止未探测直接给大段替换代码。

## 十四、失败记录（累计）

### printf 转义
- 参数里 `\s` `\d` 等被 shell 转义 → 用辅助 Python 脚本改写
- 参数里 `%%` 想输出 `%` → Python 代码里直接写 `%`
- 参数里 `%%%02X` 想输出 `%`+hex → 保持原样，不要简化

### 命令执行
- 多条命令合并过长容易混入垃圾 → 优先单条，必要时才合并
- 终端回显卡死 → Ctrl+C / Ctrl+L / 重开终端
- venv 未激活时 fastapi 等库找不到 → 每条命令前 source .venv/bin/activate

### grep 与替换
- grep 无输出不一定是错误，要看退出码和上下文
- replaced: 0 表示目标字符串不存在，可能已经改过，先 grep 确认
- grep -A3 找不到，可能前面已用脚本改掉，用 grep 关键词确认

### AI 行为
- 修改前必须探测现状（cat / grep / wc）
- 禁止未探测给大段替换代码
- 失败后记录到本节

## 十五、部署流程

### 顺序

1. 本地开发：改代码
2. 本地验证：venv + uvicorn，curl / 浏览器全流程跑通
3. 本地通过后：git push
4. NAS：git pull → docker compose build → up -d
5. NAS 验证：curl / 浏览器

### 禁止

- 未本地验证直接推 NAS
- 本地没跑通就 build 镜像

### 镜像传递（可选，本地有 docker 时）

- 本地 buildx 构建 arm64 镜像
- docker save 成 tar
- scp 到 NAS，docker load
- 优点：NAS 不用装编译依赖、构建快
- 缺点：本地需 Docker Desktop + WSL integration + buildx

## 十六、Calibre 联动

docker-compose.calibre.yml 编排三个服务：

- weread-downloader：下载工具，输出到 /vol1/1000/书籍中心/微信读书-书架
- auto-import：扫 import 目录，calibredb add 进 Calibre 书库
- calibre-web：书库展示 :9883

关联点：weread 的 OUTPUT_DIR == auto-import 的 /import == Calibre 输入目录

首次部署前必须先初始化 Calibre 书库（生成 metadata.db）。
auto-import 用 imported.txt 记录已导入清单，避免重复。
