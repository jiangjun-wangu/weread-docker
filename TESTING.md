# 测试标准（TESTING.md）

> 每轮开发完成、提交前必跑。判定不通过 → 停，修复后再提交。

## 〇、环境自检与依赖安装（新会话/新机器首跑）

与 CONVENTIONS.md 〇 节同脚本，幂等，可重复跑。

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
