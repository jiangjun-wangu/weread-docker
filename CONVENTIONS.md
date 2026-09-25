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
| NOTES.md | 给开发者看：协议、模块、规范 | 每轮开发 |
| HANDOFF.md | 给新会话看：进度、待办 | 会话切换时 |
| CONVENTIONS.md | 本文件，开发规范 | 规范变更时 |
| TESTING.md | 测试标准：健康检查、API 清单、端到端、专项 | 测试标准变更时 |
| DEPLOY.md | ARM 构建推送 GHCR 完整流程 | 部署流程变更时 |

### 8.2 更新时机（MUST）

- 新增文件 → NOTES.md 记录
| 新增依赖 → README + requirements.txt
| 改动流程 → NOTES.md
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
先读 ~/weread-docker/CONVENTIONS.md、NOTES.md、HANDOFF.md。
代码在 ~/weread-docker，git 已关联 GitHub。
遵守 CONVENTIONS.md 的开发规范。
从 HANDOFF.md 的"下一步"继续。
先跑环境自检与依赖安装（〇 节）。
再跑健康检查确认环境（TESTING.md 第一节）。
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

