# Eleven Memory Agent Platform (EMAP)

EMAP 是一个可运行的记忆增强 Agent 后端 MVP，内置 RAG 主链路，当前重点解决四件事：

- 文档导入与切片
- `BM25 + FAISS + CrossEncoder reranker` 混合检索
- 带引用问答与基础安全降级
- MySQL / Redis / FAISS 分层存储与最小评测闭环

一句话定位：**这不是“只会调 LLM API”的 Demo，而是一个已经跑通导入、检索、问答、记忆、评测、测试的 AI 后端骨架。**

## 当前状态

当前仓库是 **高质量 MVP / 工程化骨架**，不是生产终态。

已经落地：

- FastAPI 后端入口与 REST API
- 文档导入、切片、重建索引
- `BM25 + FAISS + reranker` 混合检索
- 带来源引用的问答输出
- 偏好记忆（MySQL）与短时会话（Redis）
- 输入审查、输出引用校验、权限前缀过滤、审计日志
- 离线评测脚本与基础质量门禁
- 单元测试、E2E 测试、可选真实依赖集成测试

暂未完成或仍偏 MVP：

- 真实独立向量库适配
- 更完整的知识记忆编辑 / 删除 / 追溯闭环
- 真实生产级日志、监控、限流、降级体系
- CI 中自动跑真实依赖集成测试

## 技术栈

- Python 3.12 / 3.13
- FastAPI
- LangChain
- MySQL
- Redis
- FAISS
- sentence-transformers
- uv

## 仓库结构

```text
Eleven-RAG/
├─ AGENTS.md
├─ BACKEND_GUIDE.md
├─ README.md
├─ pyproject.toml
├─ .env.example
├─ scripts/
│  ├─ start.ps1
│  ├─ manage_memory_schema.py
│  ├─ rebuild_faiss_index.py
│  ├─ evaluate_rag.py
│  └─ prepare_eval_corpus.py
├─ eval/
│  ├─ sample_dataset.jsonl
│  └─ e2e_dataset.jsonl
└─ eleven-agent-platform/
   ├─ main.py
   ├─ agent_system/
   ├─ audit/
   ├─ authz/
   ├─ controllers/
   ├─ core/
   ├─ document_processing/
   ├─ embedding/
   ├─ evaluation/
   ├─ guards/
   ├─ qa/
   ├─ repositories/
   ├─ schemas/
   ├─ services/
   ├─ tests/
   └─ vector_storage/
```

说明：

- `eleven-agent-platform` 是唯一后端主入口
- `qa/answering.py` 负责问答主编排，内部已拆成检索编排和回答生成协作对象
- `vector_storage/FaissVectorStore` 是当前实际向量存储适配层
- `tests/` 同时包含单测、E2E 和可选集成测试

## 核心能力

### 1. 文档导入

- 支持文本直接导入
- 支持本地 `.md / .txt / .pdf` 文件导入
- 支持 `recursive / markdown / sentence` 三种切片策略
- 重复导入同一 `document_id` 时会替换旧 chunk 并同步重建索引

### 2. 混合检索

当前检索链路：

1. BM25 关键词召回
2. FAISS 向量召回
3. CrossEncoder reranker 重排
4. 按配置权重融合返回 topK

当前实现是“真实混合检索”，不是 README 里喊口号。

### 3. 带引用问答

- `chat` 先检索证据，再生成答案
- 关键结论要求携带 `chunk_id` 引用
- LLM 不可用时走模板化兜底回答
- 引用不合法时会被输出校验降级成“证据式回答”

### 4. 记忆与权限

- 偏好记忆落 MySQL
- 短时会话落 Redis
- 支持 `USER_DOC_PERMISSIONS` 前缀级权限过滤
- 支持输入审查、输出校验、审计日志

### 5. 评测与测试

- 支持离线 RAG 指标评估
- 有单元测试与流程测试
- 有可选真实依赖集成测试

## 快速开始

### 1. 安装依赖

推荐 Python `3.12`。

```bash
uv sync --python 3.12
```

如需评测依赖：

```bash
uv sync --python 3.12 --group eval
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，至少确认这些字段：

```env
MYSQL_DSN=mysql+pymysql://root:password@127.0.0.1:3306/eleven_rag?charset=utf8mb4
REDIS_URL=redis://127.0.0.1:6379/0
EMBEDDING_MODEL_NAME=BAAI/bge-m3
RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3
```

如果要启用真实 LLM：

```env
LLM_ENABLED=true
LLM_API_BASE=你的网关地址
LLM_API_KEY=你的密钥
LLM_MODEL=mimo-pro
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=1024
LLM_TIMEOUT_SECONDS=60
```

### 3. 初始化 memory schema

查看迁移状态：

```bash
uv run --python 3.12 python scripts/manage_memory_schema.py --action status
```

预演执行：

```bash
uv run --python 3.12 python scripts/manage_memory_schema.py --action apply --dry-run
```

执行迁移：

```bash
uv run --python 3.12 python scripts/manage_memory_schema.py --action apply
```

### 4. 启动服务

PowerShell 一键启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

默认会自动执行：

1. `uv sync --python 3.12`
2. MySQL / Redis 连通性检查
3. memory schema 应用
4. 启动 FastAPI

常用参数：

- `-SkipSync`
- `-SkipInfraCheck`
- `-SkipMemorySchema`
- `-NoReload`
- `-Port 9000`
- `-PythonVersion 3.12`

手动启动：

```bash
uv run --python 3.12 uvicorn main:app --app-dir eleven-agent-platform --reload --port 8000
```

首次启动会预热 embedding 模型并缓存到 `.rag_store/models`。

### 5. 健康检查

```bash
curl http://127.0.0.1:8000/health
```

`/health` 会返回：

- 服务状态
- MySQL 连接池快照
- Redis 连接池快照
- memory 操作指标

### 6. Docker Compose 启动

仓库现在已经提供一套**最小可运行**的容器化方案，会拉起：

- `api`
- `mysql`
- `redis`

启动前准备：

1. 复制 `.env.example` 为 `.env`
2. 如需给容器传入额外配置，复制 `.env.docker.example` 为 `.env.docker`
3. 如需启用真实 LLM，把 `LLM_*` 配置写到 `.env.docker`
4. 如不启用 LLM，保持 `.env.docker` 中的 `LLM_ENABLED=false` 或不创建该文件即可

启动命令：

```bash
docker compose up --build
```

后台启动：

```bash
docker compose up --build -d
```

查看服务状态：

```bash
docker compose ps
```

查看 API 日志：

```bash
docker compose logs -f api
```

停止并清理容器：

```bash
docker compose down
```

说明：

- 容器内会自动等待 MySQL / Redis 就绪
- 容器内会自动执行 `memory schema` 迁移
- API 默认暴露在 `http://127.0.0.1:8000`
- MySQL 暴露在本机 `3306`
- Redis 暴露在本机 `6379`
- Compose 不再默认把本机 `.env` 注入容器，容器专用覆盖项请放在 `.env.docker`

当前已知限制：

- 首次启动可能较慢，因为需要下载 embedding / reranker 模型
- `.pdf` 解析依赖 `unstructured` 路线，容器内已补最小系统依赖，但复杂 PDF 仍可能需要额外调试
- 这套 Compose 目标是“本地快速复现”，不是生产部署模板

## 常用命令

### CLI 提问

```bash
uv run --python 3.12 python eleven-agent-platform/nailong_cli.py "什么是RAG？"
```

强制触发词模式：

```bash
uv run --python 3.12 python eleven-agent-platform/nailong_cli.py --require-trigger "奶龙 什么是RAG？"
```

### 本地文件导入

```bash
uv run --python 3.12 python eleven-agent-platform/nailong_ingest.py docs/intro.md
```

可选参数：

- `--document-id your-doc-id`
- `--source local-file`
- `--base-url http://127.0.0.1:8000`
- `--chunk-strategy recursive|markdown|sentence`
- `--chunk-size 500`
- `--chunk-overlap 100`

### 重建 FAISS 索引

```bash
uv run --python 3.12 python scripts/rebuild_faiss_index.py
```

### 准备评测语料

```bash
uv run --python 3.12 python scripts/prepare_eval_corpus.py
```

### 执行离线评测

```bash
uv run --python 3.12 python scripts/evaluate_rag.py --dataset eval/sample_dataset.jsonl
```

带约束门禁示例：

```bash
uv run --python 3.12 python scripts/evaluate_rag.py \
  --dataset eval/sample_dataset.jsonl \
  --min-retrieval-hit-rate 0.8 \
  --min-context-precision 0.7 \
  --min-context-recall 0.7 \
  --min-citation-coverage 0.6
```

## API 概览

### `POST /v1/ingest`

请求体：

```json
{
  "document_id": "doc-001",
  "content": "RAG is retrieval augmented generation ...",
  "source": "manual",
  "chunk_strategy": "recursive",
  "chunk_size": 500,
  "chunk_overlap": 100
}
```

返回：

```json
{
  "document_id": "doc-001",
  "chunk_count": 3
}
```

### `POST /v1/retrieve`

请求体：

```json
{
  "query": "what is rag",
  "top_k": 5
}
```

返回字段包含：

- `chunk_id`
- `document_id`
- `content`
- `score`

### `POST /v1/chat`

请求体：

```json
{
  "user_id": "u1",
  "session_id": "s1",
  "query": "什么是 RAG？",
  "top_k": 5
}
```

返回：

- `answer`
- `sources[]`

### 偏好记忆

- `POST /v1/memory/preferences`
- `GET /v1/memory/preferences/{user_id}`

## 测试说明

### 默认测试

默认 `pytest` 跑的是单元测试 + E2E 测试，不依赖真实 MySQL / Redis：

```bash
uv run --python 3.12 pytest
```

### 真实依赖集成测试

仓库已经提供了真实依赖集成测试，但默认关闭，避免把日常开发环境绑死。

开启方式：

```powershell
$env:EMAP_RUN_INTEGRATION_TESTS="1"
uv run --python 3.12 pytest -m integration
```

这组测试会尝试验证：

- MySQL 元数据 `replace_chunks` 替换一致性
- MySQL + Redis 的偏好 / 会话记忆读写
- FAISS 索引文件的索引、删除、重建、检索闭环

注意：

- 需要本机可访问的 MySQL 与 Redis
- 若依赖不可用，测试会自动跳过
- FAISS 集成测试使用测试向量桩，不依赖在线模型下载

## 数据流

最小主链路如下：

1. `ingest`：输入文档 -> 切片 -> 写入 MySQL 元数据 -> 写入 FAISS 索引
2. `retrieve`：BM25 -> FAISS -> reranker -> 融合打分 -> 返回候选证据
3. `chat`：检索证据 -> 权限过滤 / guard -> 回答生成 -> 输出引用校验 -> 返回答案
4. `memory`：偏好落 MySQL，会话落 Redis，并暴露健康指标

## 当前实现边界

### 已经比较像工程项目的部分

- 混合检索链路真实存在
- 记忆存储拆成 MySQL + Redis
- 输出引用可校验
- 有评测脚本
- 有单测、E2E 和 gated integration tests
- 有基础 Docker Compose 本地复现方案

### 仍然需要继续补硬骨头的部分

- 真实独立向量库
- CI 自动跑集成测试
- 更强的日志 / 监控 / 降级 / 限流
- 更完整的知识记忆治理闭环
- 更贴近生产的容器编排与镜像优化

## 推荐阅读顺序

1. `AGENTS.md`
2. `README.md`
3. `BACKEND_GUIDE.md`
4. `eleven-agent-platform/main.py`
5. `controllers/`
6. `qa/answering.py`
7. `repositories/metadata_repository.py`
8. `repositories/vector_repository.py`
9. `repositories/memory_repository.py`
10. `tests/`

## 相关文档

- `BACKEND_GUIDE.md`：后端阅读导图
- `导学-EMAP.md`：项目导学
- `面经-EMAP.md`：项目面试讲法
- `进度文档.md`：近期演进记录
