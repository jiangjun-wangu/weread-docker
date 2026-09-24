# ARM 环境 Docker 构建与推送指南

> 面向 NAS（arm64）原生构建 + 推送 GHCR 的完整流程。
> 适用：飞牛/群晖等 ARM NAS 自建镜像并分享给他人。

## 一、适用场景与架构说明

| 场景 | 说明 |
|---|---|
| 构建机 | NAS（arm64 原生），无需交叉编译 |
| 镜像架构 | 仅 linux/arm64 |
| 分发 | 推送 GHCR，他人 docker pull |

注意：NAS 构建**只能产出 arm64 镜像**。x86 机器/电脑拉取会报 no matching manifest。

## 二、前置条件

| 项 | 要求 |
|---|---|
| Docker | 20.10+（含 buildx 可选，单架构不需要 buildx） |
| 用户组 | 当前用户已加入 docker 组 |
| GHCR | 已生成 classic PAT，勾选 write:packages |
| 网络 | 能访问 ghcr.io |

## 三、首次配置

### 3.1 用户加入 docker 组

    sudo usermod -aG docker $USER

执行后退出终端重登，验证：

    id | grep docker
    docker ps

应看到 docker 组，且 docker ps 不再 permission denied。

### 3.2 登录 GHCR

PAT 生成：GitHub → Settings → Developer settings → Tokens (classic) → Generate new token (classic)，勾 write:packages。

登录：

    docker login ghcr.io -u <GitHub用户名>

Password 处粘贴 PAT，出现 Login Succeeded 即成功。凭证存于 ~/.docker/config.json。

## 四、构建 arm64 镜像

在项目根目录（含 Dockerfile）执行：

    cd /vol1/1000/Docker/weread-docker
    git pull
    docker build -t ghcr.io/<用户名>/weread-docker:v1.0.0 .

说明：

| 点 | 说明 |
|---|---|
| 无需 --platform | NAS 本身 arm64，构建即 arm64 |
| 层缓存 | 改代码只重建 COPY app 之后的层，秒级完成 |
| 基础镜像 | python:3.12-slim，首次拉取后缓存 |
| 验证 | 末尾出现 naming to ghcr.io/... 即成功 |

## 五、推送 GHCR

    docker push ghcr.io/<用户名>/weread-docker:v1.0.0

成功后输出：

    v1.0.0: digest: sha256:xxxx size: NNNN

验证远端：

    docker manifest inspect ghcr.io/<用户名>/weread-docker:v1.0.0

应看到 architecture 为 arm64、os 为 linux。

## 六、设为 public（供他人拉取）

GHCR 包默认 private，他人拉取会报 unauthorized。必须改为 public。

### 6.1 精确入口

直接打开包设置页（关键，别进错页）：

    https://github.com/users/<用户名>/packages/container/<包名>/settings

本项目：https://github.com/users/jiangjun-wangu/packages/container/weread-docker/settings

### 6.2 常见坑

| 坑 | 说明 |
|---|---|
| 进了「版本详情页」 | 点包名默认进某版本页，只有 digest/manifest，没有可见性开关 |
| 找不到 Change visibility | 它在设置页最底 Danger Zone，不在版本页 |
| 以为改 tag 就行 | 可见性是包级，不是版本级，改一次全版本生效 |

### 6.3 操作步骤

1. 打开 6.1 的 settings URL
2. 拉到最底 Danger Zone
3. 点 Change package visibility
4. 选 Public
5. 弹窗要求手动输入包名 weread-docker 确认
6. 确认

验证：包详情页顶部显示 Public 标签（原本是 Private）。

### 6.4 改完即可拉取

    docker pull ghcr.io/<用户名>/weread-docker:<tag>

无需 docker login，任何人可拉。

## 七、NAS 部署（compose 用远程镜像）

### 7.0 环境隔离铁律

| 环境 | 允许 | 禁止 |
|---|---|---|
| 本地 | 改代码、git、构建、验证 | — |
| NAS | pull 镜像、compose up/down | 改代码、手改 compose、git reset/stash |

NAS 的 compose 永远来自仓库，禁止在 NAS 上编辑。

### 7.1 仓库中的两个 compose

| 文件 | 用途 | 谁用 |
|---|---|---|
| docker-compose.yml | 生产：image 指向 GHCR | NAS |
| docker-compose.dev.yml | 开发：build . 本地构建 | 本地 |

本地开发：

    docker compose -f docker-compose.dev.yml up -d --build

NAS 部署（默认文件）：

    docker compose pull
    docker compose up -d

### 7.2 生产 compose 内容（仓库中的 docker-compose.yml）

    services:
      weread-downloader:
        image: ghcr.io/<用户名>/weread-docker:v1.0.0
        platform: linux/arm64
        container_name: weread-downloader
        environment:
          - TZ=Asia/Shanghai
          - PORT=8765
          - CONFIG_DIR=/app/config
          - OUTPUT_DIR=/app/output
          - DOWNLOAD_INTERVAL=3
          - MAX_PER_MONTH=100
          - AUTO_SYNC_ENABLED=false
          - AUTO_SYNC_INTERVAL_HOURS=6
        volumes:
          - ./config:/app/config
          - ./output:/app/output
        ports:
          - "8765:8765"
        user: "1000:1001"
        restart: unless-stopped

部署：

    docker compose pull
    docker compose up -d
    docker compose logs --tail=30

首次部署后浏览器打开 http://NAS_IP:8765 扫码登录（config/ 为空时必须重新扫码）。

## 八、日常更新流程

| 步 | 操作 | 在哪 |
|---|---|---|
| 1 | 改代码、本地验证、commit、push | 开发机 |
| 2 | git pull | NAS |
| 3 | docker build -t ghcr.io/.../weread-docker:vX.Y.Z . | NAS |
| 4 | docker push ghcr.io/.../weread-docker:vX.Y.Z | NAS |
| 5 | 改 compose 的 image tag，docker compose pull && up -d | NAS |

提示：小改动用层缓存，构建+推送通常 1 分钟内完成。

## 九、常见问题

| 现象 | 原因 | 对策 |
|---|---|---|
| permission denied docker.sock | 用户不在 docker 组 | sudo usermod -aG docker $USER 后重登 |
| denied: denied（login） | 用了 fine-grained token | 改用 classic token，勾 write:packages |
| 拉 python:3.12-slim 极慢 | 国内直连 docker.io 慢 | 配 /etc/docker/daemon.json registry-mirrors 后 systemctl restart docker |
| no matching manifest for linux/amd64 | 镜像只推了 arm64 | 在 arm64 机器构建，或本地用 buildx 多架构重建 |
| 推送后他人拉不到 | 包是 private | 改为 public（见第六节） |
| 旧容器未更新 | compose 没检测到镜像变化 | docker compose pull && docker compose up -d |
| 本地和 NAS 同登录互踢 | 微信读书单账号单 session | 同一时间只在一处登录 |
