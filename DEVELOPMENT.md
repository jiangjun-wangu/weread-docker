# 开发规范（AI 可读版）

> 本文件面向 AI 助手。每条规则含：规则、检查方式、正例、反例。
> MUST=必须遵守 SHOULD=建议遵守 MAY=可选

## 〇、AI 每轮必做

### 开轮检查（MUST）

```bash
cd ~/weread-docker && git status && git log --oneline -3
```

判定：
- 工作区干净 → 可以开始
- 有未提交改动 → 先问用户是否提交

### 终端区分（MUST）

项目有**两个终端**，命令极易贴错，执行前必须看清提示符：

| 终端 | 提示符 | 只能做什么 |
|---|---|---|
| 本地 JARVIS | `jiangjun@JARVIS:~/weread-docker$` | 改代码、git add/commit/push、本地 venv |
| NAS（生产） | `jiangjun@wxy-oes-nas:...$` | git pull、docker build、docker compose |

规则：

- 改代码 / git 提交 → **只在本地**
- 部署 / 构建镜像 → **只在 NAS**
- NAS 上所有 docker 命令**统一 sudo**（组权限不可靠）
- 命令贴错终端（如 NAS 上 `cd ~/weread-docker`）→ 立即 Ctrl+C，切回正确终端
- 贴命令前先看提示符，别凭记忆

### 终端区分（MUST）

项目有**两个终端**，命令极易贴错，执行前必须看清提示符：

| 终端 | 提示符 | 只能做什么 |
|---|---|---|
| 本地 JARVIS | `jiangjun@JARVIS:~/weread-docker$` | 改代码、git add/commit/push、本地 venv |
| NAS（生产） | `jiangjun@wxy-oes-nas:...$` | git pull、docker build、docker compose |

规则：

- 改代码 / git 提交 → **只在本地**
- 部署 / 构建镜像 → **只在 NAS**
- NAS 上所有 docker 命令**统一 sudo**（组权限不可靠）
- 命令贴错终端（如 NAS 上 `cd ~/weread-docker`）→ 立即 Ctrl+C，切回正确终端
- 贴命令前先看提示符，别凭记忆

### 环境自检与依赖安装（MUST，新机器/新会话首跑）

    clear; cd ~/weread-docker
    echo "=== 0.1 系统 ==="; uname -r | grep -q microsoft-standard-WSL2 && echo "WSL2" || echo "非 WSL2"; . /etc/os-release; echo "$PRETTY_NAME"; uname -m
    echo "=== 0.2 python3.12 ==="
    if ! command -v python3.12 >/dev/null 2>&1; then
        echo "缺 python3.12，尝试 deadsnakes 安装"
        sudo apt update && sudo apt install -y software-properties-common
        sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt update
        sudo apt install -y python3.12 python3.12-venv python3.12-dev || echo "!!! 装 3.12 失败，手动处理"
    fi
    python3.12 --version
    echo "=== 0.3 venv ==="
    [ -d .venv ] || python3.12 -m venv .venv
    source .venv/bin/activate; python3 --version
    echo "=== 0.4 依赖 ==="
    pip install --upgrade pip >/dev/null && pip install -r requirements.txt
    echo "=== 0.5 docker(可选，开发机无需) ==="
    command -v docker >/dev/null && docker --version || echo "无 docker（开发机无需，构建在 NAS）"

判定：0.2 出 Python 3.12.x；0.3 出 Python 3.12.x；0.4 无报错；0.5 记录即可。

### 修改前探测（MUST）

禁止未探测直接给替换代码。先做其一：

```bash
sed -n "起始,结束p" 文件       # 看指定行
grep -n "关键词" 文件          # 定位
cat 文件                      # 看全文
wc -l 文件                    # 看长度
```

### 修改后验证（MUST）

```bash
python3 -c "from app import 模块; print(\"OK\")"   # Python 语法
grep -n "改动关键词" 文件                         # 确认生效
```

## 一、Git 规范

### 1.1 提交六步（MUST）

提交前**必须**先本地验证并获用户确认。**第 0 步是硬门槛：用户回复 OK 前，AI 不得给出提交命令。**

| 步 | 动作 | 说明 |
|---|---|---|
| 0 | 本地验证 + 用户确认 | 浏览器/curl 通过，用户回 OK |
| 1 | 备份 | tar czf ~/weread-docker-backup-... |
| 2 | git add -A | |
| 3 | git status | 运行时数据计数必须 0 |
| 4 | git commit -m "类型: 描述" | |
| 5 | git push + git log -3 | |

命令参考：

```bash
tar czf ~/weread-docker-backup-$(date +%Y%m%d-%H%M%S).tar.gz --exclude=.git --exclude=.venv --exclude=output --exclude=config --exclude=calibre .
git add -A
git status
git commit -m "类型: 描述"
git push
git log --oneline -3
```

### 1.2 Commit Message（MUST）

格式：`类型: 中文描述`

| 类型 | 用途 | 例 |
|---|---|---|
| feat | 新功能 | feat: 下载暂停/继续 |
| fix | 修 bug | fix: 401 自动弹遮罩 |
| docs | 文档 | docs: 更新 README |
| style | 样式 | style: UI 美化 |
| refactor | 重构 | refactor: 拆分 api |
| chore | 杂项 | chore: 更新依赖 |

### 1.3 提交前检查（MUST）

```bash
git ls-files | grep -c -E "session|downloaded|rate|\.epub"
# 必须输出 0，否则有运行时数据混入
```


## 二、文件修改规范

### 2.1 分工（MUST）

| 文件类型 | 修改方式 |
|---|---|
| 所有文件 | AI 用 Python 脚本命令改 |

原则：用户只负责跑命令，不打开编辑器。

### 2.1.1 命令改文件（MUST）

禁止让用户手动编辑。用 Python 脚本：

```python
import pathlib
p = pathlib.Path("目标文件")
t = p.read_text()
t = t.replace("旧内容", "新内容", 1)
p.write_text(t)
```

或行号切片（替换整段函数）：

```python
lines = p.read_text().split(chr(10))
out = lines[:start] + new_block + lines[end:]
p.write_text(chr(10).join(out))
```

HTML/CSS/JS 也走这个流程。

### 2.2 printf 转义陷阱（MUST）

- 参数里 `\\s` `\\d` 会被 shell 转义 → 用辅助 Python 脚本
- Python 代码里的 `%` 直接写 `%`，不要写 `%%`
- Python 代码里的 `%%%02X` 保持原样，不要简化

检查方式：改完后 `grep` 关键字符确认

### 2.3 Python 脚本替换模板（MUST）

```python
import pathlib
p = pathlib.Path("目标文件")
t = p.read_text()
old = "原内容"
new = "新内容"
if old in t:
    t = t.replace(old, new, 1)
    p.write_text(t)
    print("patched")
else:
    print("!!! 未匹配")
```

### 2.4 同名函数覆盖（SHOULD）

Python 里同名类/函数后定义覆盖先定义，可用于"追加即替换"。
但需要保持文件整洁，避免多个版本堆积。

### 2.5 命令格式（MUST）

- 一行命令，`clear` 开头（健康检查除外）
- 用户复制整行执行
- 检查类命令不加 clear，保留上下文
- 多命令合并用 `;` 或 `&&` 连接


### 2.6 大块写入防卡（MUST）

向文件写入大段内容（>60 行）时，必须分块，禁止一次性大 heredoc。

| 规则 | 说明 |
|---|---|
| 单块 ≤ 60 行 | 超过就拆，`cat >> 文件 << 'EOF'` 逐块追加 |
| 优先 `cat heredoc` | 不用 `python3 - <<PY`，卡住时 shell 停在 `>` 难脱困 |
| 内容禁含三反引号 | 代码块用 4 空格缩进替代，三反引号会截断粘贴 |
| 每块验证 | 跑完 `wc -l`，数字对不上立即停 |
| 卡 `>` 脱困 | Ctrl+C 两次回到提示符 |

正例：

    cat >> 文件 << 'MD_EOF'
    内容（无三反引号）
    MD_EOF
    wc -l 文件

反例：

    python3 - <<'PY'
    ...长内容含 ```bash...
    PY

## 三、Python 规范

### 3.1 目录结构（MUST）

```
app/
  __init__.py
  __main__.py      入口（python -m app）
  main.py          CLI 入口
  api.py           FastAPI 接口
  config.py        环境变量 + settings
  logger.py        日志缓冲
  protocol.py      协议核心（纯函数）
  auth.py          扫码登录
  client.py        HTTP 封装
  store.py         数据持久化
  epub.py          EPUB 打包
  downloader.py    下载引擎
  static/          前端资源
```

### 3.2 导入顺序（MUST）

1. 标准库（import os, import json）
2. 第三方库（import httpx）
3. 本项目（from app import xxx）

组间空一行。

### 3.3 命名（MUST）

| 类型 | 风格 | 例 |
|---|---|---|
| 模块 | 小写下划线 | downloader.py |
| 类 | 大驼峰 | WeReadClient |
| 函数/变量 | 小写下划线 | download_book |
| 常量 | 全大写下划线 | OUTPUT_DIR |
| 私有 | 前缀下划线 | _download_worker |

### 3.4 异常处理（MUST）

- 自定义异常放模块顶部
- 捕获具体异常，禁止裸 `except:`
- 关键路径记录日志：`log.exception(...)`

### 3.5 环境变量（MUST）

所有配置通过环境变量，默认值写在 `config.py`：

```python
PORT = int(os.environ.get("PORT", "8765"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "output"))
```

### 3.6 依赖管理（MUST）

- 依赖写 `requirements.txt`
- 本地用 venv，禁止 `--break-system-packages`
- 每次跑 Python 前 `source .venv/bin/activate`


### 3.7 数据库规范（MUST）

- 数据库：SQLite（`config/weread.db`），表结构集中在 `schema.sql`
- 连接：`app/db.py`（线程局部 + WAL），用 `query/query_one/execute/executemany`
- 建表：`db.init_db()`（幂等，读 schema.sql）
- 类型：只用 TEXT/INTEGER/BLOB；时间统一整数时间戳（秒）
- 主键：业务 ID，不用自增（便于迁移）
- 索引：命名 `idx_表_字段`；换 MySQL 只改 db.py 连接层
- 迁移：旧 JSON → DB 用 `store.migrate_from_json()`（幂等，DB 有则不覆盖）
- 新增数据一律进 DB，不再写 JSON 文件

## 四、前端规范

### 4.1 文件组织（MUST）

```
app/static/
  index.html   单页结构
  style.css    全站样式
  app.js       前端逻辑
```

无构建，无 npm，原生 HTML/CSS/JS。

### 4.2 命名（MUST）

| 类型 | 风格 | 例 |
|---|---|---|
| class | 短横线 | progress-bar |
| id | 短横线 | btn-pause |
| JS 变量 | 小驼峰 | downloadSSE |
| JS 函数 | 小驼峰 | renderProgress |

### 4.3 样式（SHOULD）

- CSS 变量定义主题色（:root）
- 主色 `#2762D9`（微信读书蓝）
- 卡片圆角 12px，按钮圆角胶囊
- 白底，无重阴影，用边框区分

### 4.4 JS 规范（MUST）

- `$` / `$$` 简写 querySelector
- `api()` 统一 fetch 封装，抛带 `status` 的 Error
- SSE 用 EventSource，关闭时机明确
- 按钮绑定写在文件末尾统一区

### 4.5 前端修改方式（MUST）

HTML/CSS/JS 有大量特殊字符，禁止 printf 直接写。

流程：
1. AI 给完整内容
2. 用户在 VSCode 粘贴保存
3. AI 用 grep 验证关键行

例外：小段精确替换可用 Python 脚本（第 2.3 节模板）。


## 五、Docker 规范

### 5.1 基础镜像（MUST）

- `python:3.12-slim`（官方 arm64）
- `platform: linux/arm64`
- 非 root 运行：`user: "1000:1001"`

### 5.2 Dockerfile 结构（MUST）

```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1 \\
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
RUN mkdir -p /app/config /app/output && chmod -R a+rX /app/app
ENV CONFIG_DIR=/app/config \\
    OUTPUT_DIR=/app/output \\
    PORT=8765
EXPOSE 8765
CMD ["python", "-m", "app.api"]
```

### 5.3 数据卷（MUST）

- `./config` 挂 `/app/config`（运行时数据，不进镜像）
- `./output` 挂 `/app/output`（EPUB 输出）
- 禁止把运行时数据打进镜像

### 5.4 权限（MUST）

- 容器内用户 uid=1000 gid=1001（与 NAS 用户一致）
- 镜像内 `/app/app` 要 `chmod -R a+rX`（否则非 root 读不到）
- 宿主机 `./config` `./output` 属主 `1000:1001`

### 5.5 部署顺序（MUST）

1. 本地开发
2. 本地验证（venv + uvicorn + curl + 浏览器）
3. `git push`
4. NAS 构建 arm64 镜像并推送 GHCR
5. NAS `docker compose pull`
6. NAS `docker compose up -d`
7. NAS 验证

禁止：本地没跑通就推 NAS。

### 5.6 compose 文件（MUST）

| 文件 | 用途 | 谁用 |
|---|---|---|
| docker-compose.yml | 生产：仅引用 GHCR 镜像（无 build） | NAS |
| docker-compose.dev.yml | 开发：build . 本地构建 | 本地 |
| docker-compose.calibre.yml | 下载 + Calibre + auto-import 联动 | NAS |

### 5.7 环境隔离铁律（MUST）

| 环境 | 允许 | 禁止 |
|---|---|---|
| 本地 JARVIS | 改代码、git 操作、本地验证、构建镜像 | — |
| NAS（生产） | pull 镜像、构建 arm64 镜像并 push GHCR、compose up/down | **改代码、git 改文件、手改 compose、git reset/stash** |

铁律：

1. NAS 不是开发环境，任何代码/配置文件变更都在本地做完再 push
2. NAS 的 compose 必须来自仓库，禁止在 NAS 上 `cat >` 或编辑
3. 违反后果：仓库与生产漂移、数据目录被误操作（已发生一次）
4. NAS 上唯一允许的 git 操作：`git pull`（且仅当该目录仍是 git 工作区时）

违反本条的 AI 操作，用户应立即叫停。

补充（NAS docker 权限）：

- NAS 上所有 docker / docker compose 命令**统一用 `sudo`**
- 原因：docker 组权限不可靠（重登后仍可能拒），不要折腾加组
- 示例：`sudo docker build` / `sudo docker compose up -d` / `sudo docker push`


## 六、API 规范

### 6.1 路径（MUST）

- 统一前缀 `/api/`
- RESTful：GET 读，POST 写
- 资源用名词复数：`/api/records`
- 操作型用动词：`/api/download/pause`

### 6.2 响应（MUST）

- 成功：直接返回数据 JSON
- 失败：`{"detail": "错误信息"}` + 合适的 HTTP 状态码

| 状态码 | 含义 |
|---|---|
| 200 | 成功 |
| 400 | 参数错 |
| 401 | 未登录/session 过期 |
| 409 | 冲突（已有任务） |
| 500 | 服务器错 |

### 6.3 session 过期（MUST）

任何端点到 401，后端要：
1. `store.clear_session()`
2. `_reset_client()`
3. 前端 `api()` 里 `err.status === 401` → 弹遮罩

### 6.4 SSE（SHOULD）

- 下载进度：`/api/download/stream`
- 日志：`/api/logs/stream`
- 前端用 EventSource，结束时 close


## 七、安全规范

### 7.1 敏感数据（MUST）

以下文件禁止进 git：

- `config/session.json`（含 Cookie）
- `config/downloaded.json`
- `config/rate.json`
- `output/*.epub`
- `calibre/`（书库和配置）

.gitignore 必须包含，每次提交前 `git ls-files | grep -c ...` 检查。

### 7.2 输入校验（MUST）

- 所有 API 参数校验类型和范围
- 路径参数禁止 `..` 等穿越
- 文件名过滤 `/\:*?<>|` 等非法字符

### 7.3 风控（MUST）

- 请求间隔默认 3 秒
- 每月下载上限 100 次
- 单线程下载，不并发
- 见 `config.py` 的 `DOWNLOAD_INTERVAL` / `MAX_PER_MONTH`


## 八、文档规范

### 8.1 文件（MUST）

| 文件 | 用途 | 何时更新 |
|---|---|---|
| README.md | 给用户看：安装、使用、配置 | 功能变化时 |
| DEVELOPMENT.md | 开发规范 + 测试标准 + 协议 | 规范/测试变更时 |
| HANDOFF.md | 给新会话看：进度、待办 | 会话切换时 |
| DEPLOY.md | 部署流程（ARM 构建推送 GHCR） | 部署变更时 |
| DEPLOY.md | ARM 构建推送 GHCR 完整流程 | 部署流程变更时 |

### 8.2 更新时机（MUST）

- 新增文件 → README.md 或 DEVELOPMENT.md 记录
| 新增依赖 → README + requirements.txt
| 改动流程 → DEVELOPMENT.md
| 换会话前 → HANDOFF.md

### 8.3 写作（SHOULD）

- 中文
- 用表格列结构化信息
- 命令用代码块
- 避免长篇大论，优先清单


## 九、测试规范

### 9.1 本地测试流程（MUST）

```bash
cd ~/weread-docker && source .venv/bin/activate
export CONFIG_DIR=~/weread-docker/config
export OUTPUT_DIR=~/weread-docker/output
python3 -m uvicorn app.api:app --host 127.0.0.1 --port 8765
```

新终端跑 curl 验证：

```bash
curl -s http://127.0.0.1:8765/api/status
curl -s http://127.0.0.1:8765/api/shelf
curl -s http://127.0.0.1:8765/api/records
```

### 9.2 健康检查（MUST）

```bash
clear; cd ~/weread-docker; source .venv/bin/activate
git ls-files | grep -c -E "session|downloaded|rate|epub"  # 应为 0
tail -5 Dockerfile                                        # CMD api
for m in protocol config store auth client epub downloader main logger api; do
    python3 -c "from app import $m" && echo "$m OK" || echo "$m FAIL"
done
ls -la app/static/ && wc -l app/static/*
git status
```

### 9.3 端到端（MUST）

改动核心逻辑后必须：

1. 登录 → 书架 → 下载 → 文件输出
2. 浏览器 F12 无报错
3. uvicorn 日志无异常


## 十、会话交接

### 10.1 触发（MUST）

会话使用率接近 90% 时主动提醒用户。

### 10.2 交接文档（MUST）

HANDOFF.md 必含：

1. 项目概述
2. 仓库与路径
3. 已完成的模块
4. 本地验证结果
5. 待办
6. 关键决策
7. 下一步

### 10.3 新会话开场提示（MUST）

```
继续微信读书 Docker 下载工具开发。
先读 ~/weread-docker/DEVELOPMENT.md、HANDOFF.md。
代码在 ~/weread-docker，git 已关联 GitHub。
遵守 DEVELOPMENT.md 的开发规范。
从 HANDOFF.md 的"下一步"继续。
先跑环境自检与依赖安装（〇 节）。
再跑健康检查确认环境（DEVELOPMENT.md 测试标准节）。
```

### 10.4 提交交接文档（MUST）

生成后必须 git add + commit + push。


## 十一、常见坑（MUST 检查）

### 11.1 printf 转义

| 现象 | 原因 | 对策 |
|---|---|---|
| 正则里 `\\s` 没了 | shell 吃反斜杠 | 用 Python 脚本改 |
| `%%` 变成 `%` | printf 格式解析 | Python 代码里直接写 `%` |
| `%%%02X` 少一个 `%` | 误把字面 `%` 简化 | 保持三百分号 |

### 11.2 命令执行

| 现象 | 原因 | 对策 |
|---|---|---|
| 终端回显卡死 | 复制粘贴混入文档 | 只复制代码块 |
| `command not found` | 命令被文档内容污染 | Ctrl+C 清空，重开终端 |
| `address already in use` | 旧进程未杀 | `pkill -f uvicorn` |
| `No module named fastapi` | venv 未激活 | 每条命令前 `source .venv/bin/activate` |

### 11.3 grep 与替换

| 现象 | 原因 | 对策 |
|---|---|---|
| `replaced: 0` | 字符串不存在或已改 | 先 `grep -n` 确认现状 |
| grep 无输出 | 不一定是错 | 看退出码或上下游 |
| 替换到错误位置 | 关键词重复出现 | 用上下文更长锚点或行号定位 |

### 11.4 Docker

| 现象 | 原因 | 对策 |
|---|---|---|
| `permission denied docker.sock` | 用户不在 docker 组 | `sudo` 或加组 |
| `PermissionError: /app/app` | 镜像内目录权限 | Dockerfile 加 `chmod -R a+rX` |
| 挂载文件变目录 | 宿主机文件不存在 | 先创建文件再挂载 |
| 输出文件属主 root | 容器 user 未指定 | compose 加 `user: "1000:1001"` |

### 11.5 session 互踢

- 微信读书单账号单 session
- 本地和 NAS 同时登录会互相踢
- 本地开发时 NAS 停用，或本地用完清 session

### 11.6 数据安全

- 每次提交前 `git ls-files | grep -c -E "session|downloaded|rate|epub"` 必须为 0
- 部署前确认 config/ output/ 只有 .gitkeep
- 新机器首次必须重新扫码


---

# 测试标准


> 每轮开发完成、提交前必跑。判定不通过 → 停，修复后再提交。

## 〇、环境自检与依赖安装（新会话/新机器首跑）

幂等，可重复跑。

    clear; cd ~/weread-docker
    echo "=== 0.1 系统 ==="; uname -r | grep -q microsoft-standard-WSL2 && echo "WSL2" || echo "非 WSL2"; . /etc/os-release; echo "$PRETTY_NAME"; uname -m
    echo "=== 0.2 python3.12 ==="
    if ! command -v python3.12 >/dev/null 2>&1; then
        echo "缺 python3.12，尝试 deadsnakes 安装"
        sudo apt update && sudo apt install -y software-properties-common
        sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt update
        sudo apt install -y python3.12 python3.12-venv python3.12-dev || echo "!!! 装 3.12 失败，手动处理"
    fi
    python3.12 --version
    echo "=== 0.3 venv ==="
    [ -d .venv ] || python3.12 -m venv .venv
    source .venv/bin/activate; python3 --version
    echo "=== 0.4 依赖 ==="
    pip install --upgrade pip >/dev/null && pip install -r requirements.txt
    echo "=== 0.5 docker(可选，开发机无需) ==="
    command -v docker >/dev/null && docker --version || echo "无 docker（开发机无需，构建在 NAS）"

| 项 | 判定 |
|---|---|
| 0.2 python3.12 | 出 Python 3.12.x |
| 0.3 venv | 出 Python 3.12.x |
| 0.4 依赖 | 无报错 |
| 0.5 docker | 记录即可（开发机无需） |

## 一、健康检查（一键）

```bash
clear; cd ~/weread-docker; source .venv/bin/activate
echo "=== 1. 运行时数据(应为0) ==="
git ls-files | grep -c -E "session|downloaded|rate|\\.epub"
echo "=== 2. Dockerfile CMD ==="; tail -5 Dockerfile
echo "=== 3. 模块 import ==="
for m in protocol config store auth client epub downloader main logger api sorter auto_sync; do
    python3 -c "from app import $m" && echo "$m OK" || echo "$m FAIL"
done
echo "=== 4. static ==="; ls -la app/static/; wc -l app/static/*
echo "=== 5. git ==="; git status; git log --oneline -3
```

| 项 | 判定 |
|---|---|
| 1 运行时数据 | 必须 `0` |
| 2 Dockerfile | `CMD ["python", "-m", "app.api"]` |
| 3 模块 import | 全部 `OK` |
| 4 static | index.html / style.css / app.js 三件在 |
| 5 git | 工作区干净或仅源码改动 |

## 二、API 端点清单

启动：`python3 -m uvicorn app.api:app --host 127.0.0.1 --port 8765`

| 端点 | 方法 | 预期 |
|---|---|---|
| `/api/status` | GET | `logged_in` + `month/used/limit` + `download{}` |
| `/api/shelf` | GET | `books[]`，支持 sort/order/filter/page |
| `/api/records` | GET | 已下载列表 |
| `/api/config` | GET | 含 `auto_sync_enabled` / `auto_sync_interval_hours` |
| `/api/config` | PUT | merge 后返回完整 settings |
| `/api/user` | GET | `userVid/nick/avatar/stats/recent` |
| `/api/download` | POST | `{book_ids:[...]}` → `{ok:true}`；已有任务 → 409 |
| `/api/download/status` | GET | `running/total/done/chapter_*` |
| `/api/download/pause` | POST | `{ok:true}` |
| `/api/download/resume` | POST | `{ok:true}` |
| `/api/download/cancel` | POST | `{ok:true}`，非即时停（见第八节） |
| `/api/sync/now` | POST | `{queued:N, book_ids:[...]}` 或 `{queued:0, reason:...}` |
| `/api/logs` | GET | `{lines:[...]}` |
| `/api/upload` | POST | multipart，落 output/，返回 `{ok,skipped,failed}` |
| `/api/outputs` | GET | 分页，排除微信已下载书 |
| `/api/outputs/{name}` | DELETE | 删 output/ 文件 |
| `/api/records/{id}/file` | DELETE | 硬删：删文件 + 删记录 |
| `/api/download/cancel/{id}` | POST | 单本取消 |
| `/api/book/{id}/intro` | GET | 简介（带缓存） |
| `/api/match` | GET | `name=文件名` → 搜微信读书，返回 bookId/title/cover/intro/rating |
| `/api/download/resume_queue` | POST | 恢复未完成队列；无未完成 → 400 |
| `/api/shelf` | GET | 支持 `nocache=1` 强制绕缓存 |
| 未登录任何端点 | — | 401 → 前端弹遮罩 |

验证命令：

```bash
for ep in status shelf records config user download/status; do
    echo "--- /api/$ep ---"
    curl -s "http://127.0.0.1:8765/api/$ep" | head -c 200; echo
done
```

## 三、前端检查清单

浏览器开 `http://127.0.0.1:8765`，F12：

| 检查点 | 预期 |
|---|---|
| Console | 无红色报错 |
| Network | 静态资源 200/304，API 200 |
| header 右侧 | 已登录时显示头像 + 昵称 |
| 书架 Tab | 列表、排序、筛选、分页可用 |
| 已下载 Tab | 记录列表 |
| 设置 Tab | 间隔秒/上限/启用自动同步/同步间隔小时/输出目录 |
| 日志 Tab | SSE 实时推送 |
| 我的 Tab | 头像、昵称、UID、4 统计卡、最近在读 |
| 登录遮罩 | 未登录时弹出，扫码可登录 |

## 四、端到端流程

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 登录 | 扫码 | status `logged_in:true` |
| 2 书架 | 打开书架 Tab | 书目数 = 微信读书 App |
| 3 下载 | 勾选 1-2 本 → 下载 | 进度条走，日志推进 |
| 4 输出 | 等完成 | `output/书名 - 作者.epub`，>1KB |
| 5 记录 | 查已下载 | 新书在列，`downloaded.json` +1 |
| 6 增量 | 再下同书 | 结果 `skipped` |

## 五、auto_sync 专项

| 场景 | 操作 | 预期 |
|---|---|---|
| 默认关 | 启动 uvicorn | 日志 `enabled=False`，不自动触发 |
| 触发 | `POST /api/sync/now` | `queued=N`（N=书架 − 已下载） |
| 互斥 | 下载中再 `POST /api/sync/now` | `{queued:0, reason:"busy"}` |
| 未登录 | 清 session 后触发 | `{queued:0, reason:"not_logged_in"}` |
| 无新书 | 全下完再触发 | `{queued:0, reason:"no_new"}` |
| 风控 | 触发后看日志 | 单线程、间隔 `DOWNLOAD_INTERVAL` |
| 取消 | 触发后 `cancel` | 非即时（见第八节），最终 `running:false` |

## 六、提交前检查

    cd ~/weread-docker
    git ls-files | grep -c -E "session|downloaded|rate|\.epub"   # 必须 0
    git status                                                   # 只应有源码/文档改动
    tail -3 Dockerfile                                           # CMD 为 api

## 七、Docker 验证（NAS 端）

| 检查 | 命令 | 预期 |
|---|---|---|
| 构建 | docker compose build | 无错 |
| 启动 | docker compose up -d | 容器 Up |
| 日志 | docker compose logs -f | 调度器启动日志 |
| 权限 | docker compose exec weread-downloader id | uid=1000 gid=1001 |
| 卷 | docker compose exec weread-downloader ls /app/config | settings 可写 |
| 访问 | curl http://NAS:8765/api/status | 200 |

## 八、已知非 bug 现象

| 现象 | 原因 | 处理 |
|---|---|---|
| cancel 后仍 running:true 几秒 | 取消在章节边界检查，当前章节请求未完 | 等当前章节完，或看日志确认 |
| queued 数 > 书架 − 已下载 | downloaded.json 含书架已下架的书 | 正常，说明历史记录更多 |
| 下载中 chapter_done 跳变大 | 章节大小不均 | 正常 |
| /api/user 头像不显示 | 微信 CDN 防盗链 | 不影响功能 |
| 本地 + NAS 同登录互踢 | 单账号单 session | 本地开发时 NAS 停用 |

## 九、验证方法论

| 规则 | 说明 |
|---|---|
| 区分触发源 | "看到数据"≠"补丁生效"，可能是别的代码路径触发的 |
| 双证法 | 探测代码逻辑 + 看 uvicorn 日志，两条都符合才算数 |
| 最小验证路径 | 只走被改动的那条路径，别绕路，绕路得出的"正常"无效 |
| 前端改动 | 必须 Ctrl+Shift+R 强刷，F5 可能吃缓存 |
| 复现 bug 场景 | 修 bug 要先能复现原场景（如登录后才加载，就得先登出再登入） |
| 后端改动 | curl 直测端点，不依赖前端页面 |


---

# 微信读书协议核心

## 二、协议核心

- 登录：GET /api/auth/getLoginUid → 二维码 → 轮询 getLoginInfo
- Cookie：wr_vid、wr_skey、wr_rt（HTTP 响应 Set-Cookie 自动收）
- 书架：GET /web/shelf/sync，errcode -2012 表示 session 过期
- 目录：POST /web/book/chapterInfos，body bookIds 数组
- referer：/web/reader/{encodeId(bookId)}k{encodeId(chapterUid)}
- 分片：POST /web/book/chapter/e_0、t_0、t_1、e_1、e_3
- 解码顺序：copyShardBody → reverseSwaps → Base64UrlDecoder
- 类型判定：PK 魔数 → EPUB；bookId 存在 → 文本型；否则 EPUB 型
