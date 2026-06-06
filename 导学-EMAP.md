# 导学：EMAP

> 已确认输入：简称采用 `EMAP`，来源于仓库名 `Eleven Memory Agent Platform`。以下内容全部基于当前仓库中的 README、代码实现、测试与脚本整理，不额外虚构线上数据。

## 1. 前置知识（面试高频标注）

| 知识点 | 为何需要 | 在本项目中的位置 | 高频度 |
|---|---|---|---|
| FastAPI 路由与依赖装配 | 要先看懂 API 入口、请求模型和服务装配方式 | `eleven-agent-platform/main.py`、`eleven-agent-platform/controllers/`、`eleven-agent-platform/services/container.py` | 高 |
| Controller / Service / Repository 分层 | 面试一定会问你为什么不把逻辑直接写在接口里 | `eleven-agent-platform/controllers/`、`eleven-agent-platform/services/`、`eleven-agent-platform/repositories/` | 高 |
| MySQL 表设计与重试 | 文档元数据、偏好记忆都落在 MySQL，涉及 schema、重试和一致性 | `eleven-agent-platform/repositories/metadata_repository.py`、`eleven-agent-platform/repositories/memory_repository.py` | 高 |
| Redis 会话缓存与 TTL | 会话记忆不直接塞 prompt，而是先做短时状态管理 | `eleven-agent-platform/repositories/memory_repository.py`、`eleven-agent-platform/services/container.py` | 中 |
| 向量检索与 FAISS 持久化 | 这是知识召回链里的语义检索基座 | `eleven-agent-platform/repositories/vector_repository.py` | 高 |
| BM25 + 向量 + Reranker 混合检索 | 这是项目最像“工程化 RAG”而不是 Demo 的地方 | `eleven-agent-platform/qa/retrieval_stack.py`、`eleven-agent-platform/qa/answering.py` | 高 |
| 引用校验与安全降级 | 回答必须可追溯，且高风险问题不能直接自由生成 | `eleven-agent-platform/guards/input_guard.py`、`eleven-agent-platform/guards/output_guard.py`、`eleven-agent-platform/qa/answering.py` | 高 |
| ACL 权限过滤与审计日志 | 这是“企业内知识库”场景的核心追问点 | `eleven-agent-platform/authz/access_control.py`、`eleven-agent-platform/audit/audit_logger.py` | 高 |
| RAG 离线评测 | 面试官很爱问“你怎么证明检索和引用真的靠谱” | `eleven-agent-platform/evaluation/runner.py`、`scripts/evaluate_rag.py`、`eval/` | 高 |
| 文档切片策略 | 导入质量直接影响召回质量，属于很容易被追问的细节 | `eleven-agent-platform/document_processing/pipeline.py`、`eleven-agent-platform/tests/test_pipeline_chunk_strategy.py` | 中 |

## 2. 重点亮点与学习顺序（先看这个）

- 亮点 1：混合检索不是口头描述，而是实打实落到了主问答链里。为什么重要：这决定它是“真正做召回融合”的 RAG 后端，而不是只调一个向量库。先看哪些文件：`eleven-agent-platform/qa/answering.py`、`eleven-agent-platform/qa/retrieval_stack.py`、`eleven-agent-platform/tests/test_retrieval_hybrid.py`。建议学习顺序：先看 `answering.py` 主链，再看 `retrieval_stack.py` 的 BM25 和 reranker，最后看测试验证权重生效。
- 亮点 2：回答必须带引用，且引用不合法会被自动降级。为什么重要：这直接体现“证据优先”而不是“模型胡说也算答案”。先看哪些文件：`eleven-agent-platform/guards/output_guard.py`、`eleven-agent-platform/guards/common.py`、`eleven-agent-platform/tests/test_answering_safety.py`。建议学习顺序：先看输出校验规则，再看问答主链里 guard 的接入点。
- 亮点 3：输入安全、权限过滤、审计日志形成了一条安全侧闭环。为什么重要：企业内知识库最怕越权检索和提示词绕过。先看哪些文件：`eleven-agent-platform/guards/input_guard.py`、`eleven-agent-platform/authz/access_control.py`、`eleven-agent-platform/audit/audit_logger.py`、`eleven-agent-platform/tests/test_access_control.py`。建议学习顺序：先理解风控分类，再看 ACL 交集逻辑，最后看审计落盘。
- 亮点 4：导入链考虑了“重建索引前先删旧 chunk”的一致性问题。为什么重要：如果这个细节没处理，更新文档后会出现脏召回。先看哪些文件：`eleven-agent-platform/document_processing/pipeline.py`、`eleven-agent-platform/repositories/metadata_repository.py`、`eleven-agent-platform/repositories/vector_repository.py`。建议学习顺序：先看 `Pipeline.ingest`，再看元数据替换与 FAISS 删除/重建。
- 亮点 5：项目不是只会“跑接口”，还补了离线评测和 CI。为什么重要：这决定你能不能把项目讲成工程项目，而不是本地跑通 Demo。先看哪些文件：`scripts/evaluate_rag.py`、`eleven-agent-platform/evaluation/runner.py`、`.github/workflows/ci.yml`。建议学习顺序：先看评测入口，再看 summary 指标计算，最后看 CI 如何执行 `pytest`。

## 3. 必备知识点

- [ ] 看懂 `POST /v1/ingest`、`POST /v1/retrieve`、`POST /v1/chat`、偏好记忆接口分别走到哪个 service。
- [ ] 看懂 `IntelligentQA.ask()` 里输入审查、权限过滤、检索、生成、输出校验、审计记录的顺序。
- [ ] 看懂 BM25、FAISS、CrossEncoder reranker 各负责什么，不要混成一句“做了混合检索”。
- [ ] 看懂为什么 `output_guard` 会在缺失引用或引用不合法时改成证据式回答。
- [ ] 看懂 `Pipeline.ingest()` 为什么要先查旧 chunk、删旧向量，再替换元数据并重建索引。
- [ ] 看懂偏好记忆在 MySQL、会话消息在 Redis 的拆分理由。
- [ ] 看懂 `AccessController.resolve()` 里“用户策略前缀”和“请求前缀”的交集规则。
- [ ] 看懂 `EvaluationRunner` 输出的 `retrieval_hit_rate`、`average_context_precision`、`citation_coverage_rate`、`safety_metrics` 是怎么来的。
- [ ] 看懂当前项目哪些能力已经实现，哪些只是 README 里的后续替换点。
- [ ] 面试时要能诚实讲出当前限制：FAISS 仍是本地索引、BM25 仍是进程内计算、知识记忆编辑删除闭环还没完全成型。

## 4. 推荐阅读（结合仓库）

| 主题 | 建议阅读位置 | 预计时间 | 读完能回答什么 |
|---|---|---:|---|
| 项目全景与目标 | `README.md`、`BACKEND_GUIDE.md` | 20 分钟 | 这个项目到底是不是“记忆增强 Agent 后端”，它和普通 RAG 有什么区别 |
| API 入口与主装配 | `eleven-agent-platform/main.py`、`eleven-agent-platform/controllers/chat_controller.py`、`eleven-agent-platform/services/chat_service.py` | 20 分钟 | 一个 `/v1/chat` 请求从哪里进、最后落到哪里 |
| 问答主链 | `eleven-agent-platform/qa/answering.py` | 40 分钟 | 检索、生成、引用校验、安全降级、审计是怎么串起来的 |
| 混合检索 | `eleven-agent-platform/qa/retrieval_stack.py`、`eleven-agent-platform/tests/test_retrieval_hybrid.py` | 30 分钟 | 为什么不是只做向量召回，权重融合具体怎么落地 |
| 导入与切片 | `eleven-agent-platform/document_processing/pipeline.py`、`eleven-agent-platform/tests/test_pipeline_chunk_strategy.py` | 25 分钟 | 文档切片策略有哪些，更新文档时怎么保证索引不脏 |
| 元数据与向量存储 | `eleven-agent-platform/repositories/metadata_repository.py`、`eleven-agent-platform/repositories/vector_repository.py` | 35 分钟 | 为什么 MySQL 与向量索引分离，FAISS 如何持久化与删除 |
| 记忆系统 | `eleven-agent-platform/repositories/memory_repository.py`、`eleven-agent-platform/services/memory_service.py` | 25 分钟 | 偏好记忆和短时会话是怎么分开的，为什么不用全量 prompt |
| 安全与权限 | `eleven-agent-platform/guards/input_guard.py`、`eleven-agent-platform/guards/output_guard.py`、`eleven-agent-platform/authz/access_control.py`、`eleven-agent-platform/tests/test_answering_safety.py` | 35 分钟 | prompt injection、越权访问、伪造引用分别怎么处理 |
| 评测与 CI | `scripts/evaluate_rag.py`、`eleven-agent-platform/evaluation/runner.py`、`.github/workflows/ci.yml` | 30 分钟 | 你如何证明系统质量，如何把评测与测试接入工程流程 |

## 5. 自学提醒

如果某个文件、某段原理或某条链路你看不懂，请继续追问 AI；本 skill 负责给学习路径、阅读顺序和面试题，不提供逐行讲解。

## 6. 项目技术定位

`交叉`：主体实现是 `Python + FastAPI` 后端工程，但项目的核心价值来自 RAG、记忆、安全与评测链路，因此它不是纯 CRUD 后端，也不是只调模型的 AI Demo。

## 7. 核心原理解析

### 7.1 为什么问答主链要先检索再生成

问题：如果直接让模型自由回答，企业内知识库场景会出现“答得像真的，但没有依据”的风险。  
机制：先从 MySQL 元数据和 FAISS 向量索引里召回候选 chunk，再做 BM25、向量分和 reranker 融合排序，最后才允许生成。  
在本项目中的落点：`eleven-agent-platform/qa/answering.py` 统一编排，`eleven-agent-platform/qa/retrieval_stack.py` 提供 BM25 与 CrossEncoder reranker。

### 7.2 为什么回答必须带来源引用

问题：只返回自然语言答案，用户没法核对，审计也没法追责。  
机制：要求答案中的关键结论携带 `chunk_id`，再由 `output_guard` 校验引用是否真实命中当前 `hits`。  
在本项目中的落点：`eleven-agent-platform/guards/output_guard.py` 会在缺失引用、伪造引用时直接降级成证据式回答。

### 7.3 为什么切片策略要显式可选

问题：Markdown 文档、自然段文本、按句理解的材料，最佳切分边界并不一样。  
机制：统一入口支持 `recursive`、`markdown`、`sentence` 三类策略，用不同分隔符优先级切 chunk。  
在本项目中的落点：`eleven-agent-platform/document_processing/pipeline.py` 构造 splitter，`eleven-agent-platform/tests/test_pipeline_chunk_strategy.py` 负责验证策略与边界条件。

### 7.4 为什么偏好记忆与会话记忆分仓

问题：用户的长期偏好和一次会话里的短时上下文生命周期完全不同。  
机制：长期偏好落 MySQL，短时消息落 Redis，并通过 TTL 与最大消息数控制长度。  
在本项目中的落点：`eleven-agent-platform/repositories/memory_repository.py` 同时管理两类存储，但保持职责区分。

### 7.5 为什么高风险问题要走保守降级

问题：合规、权限、隐私类问题如果直接让 LLM 自由发挥，最容易出现泄漏和越权。  
机制：`input_guard` 先做风险分级，高风险时默认不走自由生成，而是只整理可引用证据。  
在本项目中的落点：`eleven-agent-platform/qa/answering.py` 中的 `high_risk_grounded_only` 分支，以及 `eleven-agent-platform/tests/test_answering_safety.py`。

## 8. 关键设计决策

| 决策点 | 备选 | 取舍 | 风险 | 验证 |
|---|---|---|---|---|
| 文档元数据放 MySQL，向量单独放 FAISS | 全部塞进单一向量库；或本地 SQLite 混合存 | 当前方案更利于结构化管理与后续替换独立向量库，也符合仓库约束 | 两套存储的一致性要自己维护 | 看 `Pipeline.ingest()` 是否先删旧 chunk 再重建；看 `README.md` 是否已标注后续替换点 |
| 检索采用 BM25 + 向量 + reranker | 只做向量召回；只做关键词召回 | 当前方案召回更稳，也更容易解释为什么排在前面 | BM25 仍是进程内全量计算，大规模下会吃力 | 看 `qa/answering.py` 的权重融合、`tests/test_retrieval_hybrid.py` 的排序断言 |
| 回答必须带引用 | 允许自然语言自由回答 | 当前方案更适合知识库问答、审计和复核 | 用户体验会比“随便答”保守一些 | 看 `guards/output_guard.py` 是否会拒绝伪造引用 |
| 高风险问题默认 grounded-only | 所有问题都直接走 LLM | 当前方案更稳，尤其适合合规、权限、隐私类问答 | 回答会显得不够“聪明” | 看 `tests/test_answering_safety.py` 中高风险降级场景 |
| 偏好记忆进 MySQL，会话消息进 Redis | 全放 MySQL；全放 Redis；全塞 prompt | 当前方案兼顾持久化与短时状态成本 | 还没完全覆盖知识记忆编辑/删除闭环 | 看 `memory_repository.py` 与 `AGENTS.md` 的三类记忆约束 |
| 把离线评测做成脚本和 CI 入口 | 只人工点接口；只看主观效果 | 当前方案能做回归门禁，适合持续迭代 | 真实业务集还需要继续补齐 | 看 `scripts/evaluate_rag.py`、`evaluation/runner.py`、`.github/workflows/ci.yml` |

## 9. 量化与验证（含待测，建议）

- 检索质量：建议优先跑 `uv run --python 3.12 python scripts/evaluate_rag.py --dataset eval/sample_dataset.jsonl`，关注 `retrieval_hit_rate`、`average_context_precision`、`average_context_recall`、`citation_coverage_rate`。当前仓库指标体系已打通，真实业务数据建议补充为 `(待测)`。
- 安全质量：建议在评测集里加入 `expected_refusal`、`forbidden_chunk_ids`、`allowed_doc_prefixes`，再看 `refusal_match_rate`、`citation_validity_rate`、`forbidden_chunk_leak_rate`。这是最能体现“不是裸奔 RAG”的部分。
- 切片策略效果：建议选同一份 Markdown 文档，分别用 `recursive`、`markdown`、`sentence` 导入，比较 chunk 数量、目标问题命中率和引用完整性；不要只看切得细不细，要看检索结果是否更稳。
- 向量索引一致性：建议对同一 `document_id` 连续执行两次导入，再检查是否存在旧 chunk 残留召回；验证方式可以是比对 `chunks` 表记录数、FAISS mapping 变化和同问题的返回来源。
- 会话与偏好记忆：建议通过 `/v1/memory/preferences` 写入输出偏好，再发起 `/v1/chat` 检查兜底回答是否带上偏好描述；同时观察 `/health` 返回的 `memory_metrics` 和连接池快照。
- LLM 降级链路：建议分别验证三种情形：`LLM_ENABLED=false`、LLM 输出不合法 JSON、LLM 生成了错误引用。目标不是“模型一定成功”，而是失败时系统是否还能退回到可信答案。
- 工程门禁：建议在 CI 之外再补一层离线评测门禁，例如设置 `--min-retrieval-hit-rate`、`--min-context-precision`、`--min-citation-coverage`。当前仓库已有命令入口，阈值可以先按 `(待测)` 业务样本逐步校准。
