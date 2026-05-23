# Eleven-RAG (Minimal Runnable Skeleton)

最小可运行 RAG 后端骨架，满足：

- `uv` 作为项目管理与运行工具
- FastAPI API 可直接启动联调
- 检索链路包含“关键词 + 向量式相似度 + 重排（MVP简化版）”
- 回答返回来源引用
- 阶段 A 已支持本地持久化（SQLite 元数据 + 本地向量索引）

## 1. 目录结构

```text
Eleven-RAG/
├─ AGENTS.md
├─ BACKEND_GUIDE.md
├─ 需求分析.md
├─ .env.example
├─ pyproject.toml
├─ README.md
└─ eleven-rag/
   ├─ main.py
   ├─ core/
   │  └─ config.py
   ├─ controllers/
   │  ├─ health_controller.py
   │  ├─ ingestion_controller.py
   │  ├─ retrieval_controller.py
   │  ├─ chat_controller.py
   │  └─ memory_controller.py
   ├─ services/
   │  ├─ container.py
   │  ├─ ingestion_service.py
   │  ├─ retrieval_service.py
   │  ├─ chat_service.py
   │  └─ memory_service.py
   ├─ repositories/
   │  ├─ document_repository.py
   │  └─ memory_repository.py
   └─ schemas/
      ├─ common.py
      ├─ ingestion.py
      ├─ retrieval.py
      ├─ chat.py
      └─ memory.py
```

## 2. 启动方式（uv）

### 2.0 一键启动（PowerShell，推荐）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

默认会自动执行：

1. `uv sync --python 3.12`
2. MySQL/Redis 连通性检查
3. `memory` 初始化脚本（`scripts/manage_memory_schema.py --action apply`）
4. 启动 FastAPI API（用于后续接入 QQ 机器人）

可选参数：

- `-SkipSync`：跳过依赖同步
- `-SkipInfraCheck`：跳过 MySQL/Redis 检查
- `-SkipMemorySchema`：跳过 memory schema 应用
- `-NoReload`：关闭 `uvicorn --reload`
- `-Port 9000`：指定端口
- `-PythonVersion 3.12`：指定 Python 版本

1. 同步依赖（推荐 Python 3.12 或 3.13）：

```bash
uv sync --python 3.12
```

2. 启动服务：

```bash
uv run --python 3.12 uvicorn main:app --app-dir eleven-rag --reload --port 8000
```

首次启动会预热 `BAAI/bge-m3` 并缓存到 `.rag_store/models`。

手动预热：

```bash
uv run --python 3.12 python scripts/warmup_embedding.py
```

3. 健康检查：

```bash
curl http://127.0.0.1:8000/health
```

`/health` 结果会包含 `memory` 快照（MySQL/Redis 连接池状态 + memory 操作指标）。

启用真实 LLM（MiMo Pro / OpenAI 兼容接口）：

在 `.env` 中配置：

```env
LLM_ENABLED=true
LLM_API_BASE=你的网关基础地址
LLM_API_KEY=你的密钥
LLM_MODEL=mimo-pro
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=1024
LLM_TIMEOUT_SECONDS=60
```

说明：

- `LLM_ENABLED=false` 时，`/v1/chat` 走模板化兜底回答。
- `LLM_ENABLED=true` 且 `LLM_API_BASE/API_KEY` 有效时，`/v1/chat` 会将检索片段注入 prompt 后调用 LLM 生成答案，同时继续返回 `sources[]` 供追溯。

4. 奶龙命令行提问（默认直接提问）：

```bash
uv run --python 3.12 python eleven-rag/nailong_cli.py "什么是RAG？"
```

如需强制触发词模式：

```bash
uv run --python 3.12 python eleven-rag/nailong_cli.py --require-trigger "奶龙 什么是RAG？"
```

5. 奶龙本地文件导入（.md/.txt/.pdf）：

```bash
uv run --python 3.12 python eleven-rag/nailong_ingest.py docs/intro.md
```

可选参数：

- `--document-id your-doc-id`
- `--source local-file`
- `--base-url http://127.0.0.1:8000`

## 2.1 关键概念（Embedding / bge-m3 / FAISS）

- Embedding：把文本（query、chunk）转换为语义向量，用于相似度检索。
- `BAAI/bge-m3`：本项目当前默认的 embedding 模型，负责文本向量化。
- FAISS：向量检索库，负责存储向量并执行近邻搜索，返回最相似的候选 chunk。
- 在本项目中的关系：`bge-m3` 负责“文本 -> 向量”，FAISS 负责“向量 -> TopK 相似片段”。

## 3. 核心接口

### 3.1 文档导入

- `POST /v1/ingest`
- 请求体：

```json
{
  "document_id": "doc-001",
  "content": "RAG is retrieval augmented generation ...",
  "source": "manual"
}
```

- 返回：

```json
{
  "document_id": "doc-001",
  "chunk_count": 3
}
```

### 3.2 检索

- `POST /v1/retrieve`
- 请求体：

```json
{
  "query": "what is rag",
  "top_k": 5
}
```

- 返回：`hits` 中包含 `chunk_id/document_id/content/score`

### 3.3 问答（带引用）

- `POST /v1/chat`
- 请求体：

```json
{
  "user_id": "u1",
  "session_id": "s1",
  "query": "什么是 RAG？",
  "top_k": 5
}
```

- 返回：`answer + sources[]`

### 3.4 偏好记忆

- `POST /v1/memory/preferences`
- `GET /v1/memory/preferences/{user_id}`

## 4. 最小数据流

1. `ingest`：输入文档 -> 切片 -> 写入 MySQL 元数据 -> 向量入本地索引文件。
2. `retrieve`：关键词打分 + 向量相似度 + token 向量 fallback -> 混合分数重排 -> 返回 topK。
3. `chat`：先检索证据 -> 结合用户偏好生成回答 -> 返回引用片段。
4. `memory`：维护偏好和会话短时状态（MVP内存实现）。

## 5. MVP 与生产替换点

当前为可运行骨架，生产化按以下替换：

- `repositories/metadata_repository.py`
  - MySQL（文档元数据/关系）
- `repositories/vector_repository.py`
  - 本地索引升级为 FAISS + 真实 embedding
- `repositories/memory_repository.py`
  - MySQL（长期偏好）+ Redis（短时会话）
- `services/retrieval_service.py`
  - 接入真实 embedding、BM25/关键词检索、reranker
- `services/chat_service.py`
  - 接入真实 LLM 并保留来源引用约束

## 6. 奶龙导入能力

- `eleven-rag/nailong_ingest.py` 通过 `LangChain + UnstructuredLoader` 解析 `.md/.txt/.pdf`。
- 依赖 `langchain-unstructured`、`unstructured` 和 `markdown`。
- 当前使用本地解析模式，扫描件 OCR 暂未接入。

## 7. 向量索引重建

```bash
uv run --python 3.12 python scripts/rebuild_faiss_index.py
```

## 8. Memory 初始化脚本管理

查看 memory 迁移状态：

```bash
uv run --python 3.12 python scripts/manage_memory_schema.py --action status
```

预演执行（不真正落库）：

```bash
uv run --python 3.12 python scripts/manage_memory_schema.py --action apply --dry-run
```

执行待应用脚本：

```bash
uv run --python 3.12 python scripts/manage_memory_schema.py --action apply
```

## 9. 终端快捷唤起（PowerShell）

安装快捷命令（一次即可）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-nailong-ps.ps1
```

重开终端后可直接使用：

```powershell
奶龙 这份文档讲了什么？
```

## 10. RAG 评估（RAGAS / Phoenix / LlamaIndex）

### 10.1 安装评估依赖

```bash
uv sync --python 3.12 --group eval
```

### 10.2 准备评测集

- 示例文件：`eval/sample_dataset.jsonl`
- E2E 基准语料预置：

```bash
uv run --python 3.12 python scripts/prepare_eval_corpus.py
```

- 支持字段：
  - `id` 或 `sample_id`
  - `query`（必填）
  - `reference_answer`（可选）
  - `reference_contexts`（可选）
  - `expected_chunk_ids`（可选，检索命中评估优先使用）

### 10.3 执行离线评估

默认执行本地可计算指标（不依赖外部 LLM）：

```bash
uv run --python 3.12 python scripts/evaluate_rag.py --dataset eval/sample_dataset.jsonl
```

可选参数：

- `--output .rag_store/evals/latest_eval.json`
- `--top-k 5`
- `--doc-prefix doc-e2e-`：评估隔离，仅统计 `document_id` 以该前缀开头的召回结果（可重复传参）
- `--enable-ragas`：启用 RAGAS 指标（需额外模型/推理配置）
- `--enable-phoenix`：导出 Phoenix 可读 JSONL（用于后续观测分析）
- `--phoenix-url http://127.0.0.1:6006`
- `--min-retrieval-hit-rate 0.8`
- `--min-context-precision 0.7`
- `--min-context-recall 0.7`
- `--min-citation-coverage 0.6`

约束门禁示例（不达标即失败，退出码 `2`）：

```bash
uv run --python 3.12 python scripts/evaluate_rag.py \
  --dataset eval/sample_dataset.jsonl \
  --min-retrieval-hit-rate 0.8 \
  --min-context-precision 0.7 \
  --min-context-recall 0.7 \
  --min-citation-coverage 0.6
```

### 10.4 当前输出指标

- `retrieval_hit_rate`
- `average_context_precision`
- `average_context_recall`
- `citation_coverage_rate`
- `ragas_metrics`（启用且可用时输出）
- `constraints`（阈值配置、是否通过、违规明细）

### 10.5 与 LlamaIndex 的关系

- 本仓库主编排仍保持 `LangChain`。
- `LlamaIndex` 当前作为可选评估生态依赖引入，不改动现有业务链路。
