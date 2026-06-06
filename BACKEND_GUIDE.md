# 后端导读：EMAP 仓库该怎么读

这份文档不是理想架构设计书，而是**基于当前仓库真实实现**的后端阅读指南。  
如果 README 负责回答“这项目是什么、怎么跑、怎么测”，这份导读负责回答“代码到底在哪、先看哪里、哪些是已实现、哪些还只是方向”。

## 1. 先用一句话理解后端

当前的 `eleven-memory-agent-platform` 是一个 **记忆增强 Agent 后端 MVP**：

- 用 FastAPI 提供接口
- 用 MySQL 存文档元数据和偏好记忆
- 用 Redis 存短时会话
- 用 FAISS 做本地向量索引
- 用 `BM25 + FAISS + CrossEncoder reranker` 做混合检索
- 用引用校验、权限过滤、输入/输出 guard 保证回答尽量可追溯、可控

它已经不只是“调一次 LLM 接口”，但也还没到生产级平台。

## 2. 当前代码结构怎么理解

当前后端主入口在 `eleven-agent-platform/` 下，核心目录如下：

```text
eleven-agent-platform/
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

建议按下面这个依赖方向理解：

```text
controller -> service / agent facade -> repository / qa / guards
main 负责启动和路由装配
tests 负责锁住关键行为
```

注意两点：

1. 这个仓库不是纯粹的 `controller -> service -> repository` 教科书结构，因为问答主链路还有一层 `qa/answering.py` 编排。
2. `agent_system/facade.py` 是一个门面层，对 CLI、controller 和其他调用方隐藏底层细节。

## 3. 先看哪些文件最值钱

如果你时间有限，优先看这几处：

1. `eleven-agent-platform/main.py`
2. `eleven-agent-platform/controllers/chat_controller.py`
3. `eleven-agent-platform/qa/answering.py`
4. `eleven-agent-platform/qa/retrieval_stack.py`
5. `eleven-agent-platform/document_processing/pipeline.py`
6. `eleven-agent-platform/repositories/metadata_repository.py`
7. `eleven-agent-platform/repositories/vector_repository.py`
8. `eleven-agent-platform/repositories/memory_repository.py`
9. `eleven-agent-platform/tests/test_answering_safety.py`
10. `eleven-agent-platform/tests/test_ingest_retrieve_chat_e2e.py`

原因很直接：

- `main.py` 决定服务怎么装起来
- `chat_controller.py` 代表真实问答入口
- `qa/answering.py` 是当前最核心的业务编排
- 三个 repository 决定数据怎么进、怎么存、怎么查
- 对应测试能告诉你这些实现是不是“真跑过”

## 4. 主链路现在到底怎么走

### 4.1 启动链

入口文件是 `eleven-agent-platform/main.py`。

它做了三件事：

1. 创建 FastAPI 应用
2. 挂载 `health / ingest / retrieve / chat / memory` 路由
3. 在启动时预热 embedding

你可以把它理解成“后端总装配点”。

### 4.2 文档导入链

当前真实链路：

```text
POST /v1/ingest
  -> controllers/ingestion_controller.py
  -> services/ingestion_service.py
  -> document_processing/pipeline.py
  -> repositories/metadata_repository.py
  -> repositories/vector_repository.py
```

这里最值得看的不是 controller，而是 `document_processing/pipeline.py`：

- 负责切片策略选择
- 负责替换同一文档旧 chunk
- 负责先删旧索引再写新索引

这部分直接决定了“重复导入同一个文档时会不会脏数据残留”。

### 4.3 检索链

当前真实链路：

```text
retrieve/chat
  -> qa/answering.py
  -> qa/retrieval_stack.py
  -> metadata_repository.list_chunks()
  -> vector_repository.query()
  -> reranker.score()
```

现在已经不是“只有向量检索”：

1. BM25 做关键词召回
2. FAISS 做向量召回
3. reranker 做重排
4. 最后按权重融合分数

对应代码重点：

- `qa/retrieval_stack.py`
- `qa/answering.py` 中的 `RetrievalOrchestrator`

### 4.4 问答链

当前真实链路：

```text
POST /v1/chat
  -> controllers/chat_controller.py
  -> agent_system/facade.py
  -> qa/answering.py
  -> guards + authz + memory + llm/fallback
```

这里的关键不是“有没有 LLM”，而是**回答前后做了哪些约束**：

- 输入先过 `InputGuard`
- 文档范围先过 `AccessController`
- 命中证据后再决定是 LLM 回答还是 fallback
- 输出还要过 `OutputGuard`
- 最后写审计日志和会话记录

这说明项目已经开始关注“回答可控”，不只是“能答出来”。

## 5. `qa/answering.py` 为什么最重要

这个文件是当前后端最核心的业务编排点。

最近已经做过一轮重构，现在内部主要拆成三层角色：

- `IntelligentQA`
  作用：总门面，对外暴露 `retrieve()` 和 `ask()`
- `RetrievalOrchestrator`
  作用：负责混合检索编排
- `AnswerGenerator`
  作用：负责回答生成、fallback、LLM 输出解析

这轮拆分的意义是：

- 不改对外接口
- 降低单文件里一坨逻辑的耦合度
- 让“检索”和“生成”职责更清楚

但也要老实说：  
`IntelligentQA` 现在仍然负责 guard、权限、trace、审计、memory 编排，所以它还是偏重，后面还可以继续拆。

## 6. 三个 repository 现在分别干什么

### 6.1 `MetadataRepository`

文件：`repositories/metadata_repository.py`

当前职责：

- 建表
- upsert 文档元数据
- 替换某个文档下的全部 chunk
- 查询全量 chunk 或按文档查询 chunk

它是导入链和检索链的 MySQL 元数据基础。

### 6.2 `VectorRepository`

文件：`repositories/vector_repository.py`

当前职责：

- 管理 FAISS 索引文件
- 管理 `chunk_id -> faiss_id` 映射
- 向量化文本并写入索引
- 删除指定 chunk 的向量
- 执行向量查询

注意：

- 当前是真实 FAISS 实现
- 当前向量存储适配层名叫 `FaissVectorStore`
- 还不是独立远端向量库

### 6.3 `MemoryRepository`

文件：`repositories/memory_repository.py`

当前职责：

- MySQL 偏好记忆写读
- Redis 会话消息写读
- 简单重试
- 操作耗时 / 失败指标快照

它已经不仅是 CRUD，还加了些最小可观测性。

## 7. guards / authz / audit 这些模块值不值得看

值得，而且这是这个项目比“普通 RAG Demo”更像工程项目的地方。

### `guards/`

负责两类事：

- 输入安全检查
- 输出引用与内容校验

重点文件：

- `guards/input_guard.py`
- `guards/output_guard.py`

### `authz/`

当前实现的是**前缀级文档权限过滤**，不是完整 RBAC。

重点文件：

- `authz/access_control.py`

### `audit/`

当前实现的是本地 JSONL 审计日志，不是集中式观测系统。

重点文件：

- `audit/audit_logger.py`

这三块的现实定位要讲清楚：

- 有安全与权限意识
- 有基础落地
- 但还不是完整生产级治理系统

## 8. `agent_system/facade.py` 在当前仓库里是什么角色

它是一个**对外统一门面**。

作用：

- 给 controller / CLI / 其他调用方统一暴露能力
- 屏蔽底层 `Pipeline / IntelligentQA / MemoryService / FaissVectorStore` 细节

你可以把它理解成“轻量服务编排入口”，而不是复杂的 Agent 框架。

## 9. 测试体系现在怎么分层

当前测试大致分三层：

### 1. 单元测试

代表文件：

- `test_memory_repository.py`
- `test_metadata_repository.py`
- `test_retrieval_hybrid.py`
- `test_answering_safety.py`

主要锁住局部逻辑和边界行为。

### 2. E2E 流程测试

代表文件：

- `test_ingest_retrieve_chat_e2e.py`

这组测试会把导入、检索、问答串起来，验证不是“各模块自己觉得自己没问题”。

### 3. 真实依赖集成测试

代表文件：

- `test_live_integrations.py`

这组测试默认跳过，显式设置：

```powershell
$env:EMAP_RUN_INTEGRATION_TESTS="1"
uv run --python 3.12 pytest -m integration
```

它主要验证：

- 真实 MySQL 元数据替换
- 真实 MySQL + Redis 记忆读写
- 真实 FAISS 索引文件重建闭环

这一步很关键，因为它把“代码逻辑对”往“真实依赖也对”推进了一步。

## 10. 当前项目最应该怎么讲

如果你是开发者、面试者或接手同学，最稳的说法是：

> 这是一个已经跑通导入、混合检索、带引用问答、偏好记忆、基础安全校验和评测闭环的 AI 后端 MVP。  
> 当前重点在工程化夯实，而不是继续盲目堆功能。

这样讲的好处是：

- 不会把 MVP 吹成生产平台
- 也不会把已经做出来的工程工作说轻了

## 11. 现在还没落地的东西，不要误读

下面这些方向在仓库规则和设计目标里很重要，但**当前代码并没有完整落地**：

- 完整的知识记忆编辑 / 删除 / 追溯治理
- 独立远端向量库
- Docker / Compose 环境
- 生产级日志与监控体系
- 自动化跑真实依赖集成测试的 CI
- “新知识对照旧知识”的完整 learning 域落地

这部分可以写成“下一步演进方向”，不要写成“项目已实现能力”。

## 12. 新同学推荐阅读顺序

建议顺序：

1. `AGENTS.md`
2. `README.md`
3. `BACKEND_GUIDE.md`
4. `eleven-agent-platform/main.py`
5. `eleven-agent-platform/controllers/chat_controller.py`
6. `eleven-agent-platform/qa/answering.py`
7. `eleven-agent-platform/qa/retrieval_stack.py`
8. `eleven-agent-platform/document_processing/pipeline.py`
9. `eleven-agent-platform/repositories/metadata_repository.py`
10. `eleven-agent-platform/repositories/vector_repository.py`
11. `eleven-agent-platform/repositories/memory_repository.py`
12. `eleven-agent-platform/tests/`

## 13. 最后一句人话建议

先把这项目当成一个“已经有骨架、有主链、有测试、有边界意识”的后端工程来看。  
别一上来就追着问“为什么还没上多租户、为什么还没上远端向量库”，那是下一阶段的账；先把当前这套主链读透，含金量已经不低了。
