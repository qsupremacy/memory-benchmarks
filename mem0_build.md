# mem0 docker compose 部署 — 问题与修复记录

## 最终状态

- `memory-benchmarks-mem0-1`:Up,健康中
- `memory-benchmarks-qdrant-1`:healthy
- mem0 启动成功:`Mem0 ready (llm=openai, embedder=openai, vector_store=qdrant)`
- `curl http://127.0.0.1:8888/health` → `{"status":"ok",...}` ✅

## 问题链路与修复(按时间顺序)

### 1. 缺 `docker compose` 子命令

- 现象:`docker compose` 报 `unknown command`
- 原因:Ubuntu 24.04 的 docker-engine 包没附带 compose v2 插件
- 修复:`sudo apt-get install -y docker-compose-v2`(apt 里的 v2 包装包)

### 2. apt 默认源 + pip 默认 PyPI 在国内慢

- 现象:`apt-get install` 走 `deb.debian.org` 极慢;`pip install` 走 PyPI 也慢
- 修复:在 Dockerfile 开头加两行 sed 把 apt 源换成阿里云,pip 换成清华源

```dockerfile
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' \
        /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' \
        /etc/apt/sources.list
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. buildx 走 docker-container 驱动,不读 daemon.json 的 mirror

- 现象:虽然 `/etc/docker/daemon.json` 配了 `registry-mirrors`,但 buildx 的 buildkit 容器仍直接打 `registry-1.docker.io`
- 原因:`docker-container` 驱动跑的是独立 buildkit 进程,需要单独的 buildkit 配置
- 修复:写 `/etc/buildkit/buildkitd.toml` 配 docker.io 镜像源,然后重建 builder 时通过 `--config` 挂进去

```toml
# /etc/buildkit/buildkitd.toml
[registry."docker.io"]
  mirrors = ["https://mirror.ccs.tencentyun.com", "https://hub-mirror.c.163.com", "https://mirror.baidubce.com"]
```

```bash
docker buildx create --name multiarch --driver docker-container \
  --driver-opt "network=host" \
  --config /etc/buildkit/buildkitd.toml \
  --bootstrap --use
```

### 4. buildx 容器默认内存太小,git clone mem0ai 被 OOM 杀掉

- 现象:`pip install` 阶段 `git clone mem0ai` 时 exit 137(SIGKILL),buildx daemon 一起崩
- 原因:主机只有 3.6G 内存,buildkit 容器内再 git clone 大 ML 仓库时 OOM
- 修复:重建 buildx 容器时加内存限制

```bash
docker buildx create --name multiarch --driver docker-container \
  --driver-opt "network=host" \
  --driver-opt "memory=3g" \
  --driver-opt "memory-swap=4g" \
  --config /etc/buildkit/buildkitd.toml \
  --bootstrap --use
```

### 5. `feat/v3-pipeline` 分支在 GitHub 已不存在

- 现象:`pip install git+https://github.com/mem0ai/mem0.git@feat/v3-pipeline` 报分支找不到
- 原因:该分支已被合并/删除/改名,`git ls-remote` 也拉不到 v3 相关分支或标签
- 修复:`requirements.txt` 改成 `mem0ai==0.1.118`(PyPI 发行版,就是 v3-pipeline 合并后的正式版,host 上其他 venv 也都装的是这个)

### 6. `spacy download en_core_web_sm` 从 github.com 拉非常慢

- 现象:Dockerfile 第 8 步 `RUN python -m spacy download en_core_web_sm` 一直卡在 spacy 模型下载(github releases 慢)
- 修复:在 host 上用 `gh-proxy.com` 预下载 13M wheel,unzip 提取出包目录,放到 docker build context,Dockerfile 改用 COPY

```bash
curl -fSL -o /tmp/en_core_web_sm.whl \
  "https://gh-proxy.com/https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
unzip -q /tmp/en_core_web_sm.whl -d /tmp/spacy-model
cp -r /tmp/spacy-model/en_core_web_sm /data/disk/mem-demo/memory-benchmarks/docker/mem0/
```

```dockerfile
# Dockerfile 中替换原来 RUN python -m spacy download en_core_web_sm
COPY en_core_web_sm /usr/local/lib/python3.12/site-packages/en_core_web_sm
```

## 改动文件清单

| 文件 | 改动 |
|---|---|
| `docker/mem0/Dockerfile` | 加 apt/pip 镜像配置;移除 `spacy download` 改用 COPY 本地模型 |
| `docker/mem0/requirements.txt` | `mem0ai @ git+...feat/v3-pipeline` → `mem0ai==0.1.118` |
| `docker/mem0/en_core_web_sm/`(新) | 预下载的 spaCy en_core_web_sm 3.8.0 模型(15M) |
| `/etc/buildkit/buildkitd.toml`(新) | buildkit 镜像源配置 |

## 国内常用加速资源

- apt 镜像:`mirrors.aliyun.com`、`mirrors.tuna.tsinghua.edu.cn`
- pip 镜像:`mirrors.aliyun.com/pypi/simple/`、`pypi.tuna.tsinghua.edu.cn/simple`
- GitHub 代理:`gh-proxy.com`(本次实际可用)、`ghproxy.com`(本次超时)、`github.akams.cn`、`github.moeyy.cn`
- Docker 镜像:`mirror.ccs.tencentyun.com`、`hub-mirror.c.163.com`、`mirror.baidubce.com`
