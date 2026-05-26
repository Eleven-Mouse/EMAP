# 后端篇：`eleven-memory-agent-platform` 项目导读

## 1. 先用一句话理解后端

`eleven-memory-agent-platform` 是一个 Python + FastAPI + LangChain 的记忆增强 Agent 后端（内置 RAG），围绕“偏好记忆、知识记忆、会话记忆”三类记忆，提供文档导入、混合检索、带引用问答，以及“新知识对照旧知识”的学习型生成能力。

最关键的理解是：

- 它不只是问答接口，而是“可持续更新的记忆系统”
- 回答必须可追溯到来源，避免无依据生成
- 检索是混合策略，不是只靠向量库
- `LangChain` 只用于工作流编排和组件接入，不替代核心业务规则和数据模型

## 2. 模块结构怎么理解

本项目采用常规三层架构：`controller -> service -> repository`。

建议直接采用下面这套根目录结构：

- `main.py`
- `controllers/`
- `services/`
- `repositories/`
- `schemas/`
- `core/`
- `jobs/`
- `tests/`

推荐把依赖方向理解为：

```text
controller -> service -> repository
main 负责启动与装配
jobs 负责异步任务入口
```

也就是说：

- Controller 不承载核心业务规则
- Service 负责完整业务流程与规则编排
- Repository 负责 MySQL / 向量库 / Redis / 外部数据读写

## 3. 每一层分别负责什么

## 3.1 `controller`（接口层）

典型职责：

- 暴露 REST 接口
- 参数校验与响应序列化
- 认证信息透传（如用户 ID、租户 ID）
- 调用 Service 并返回统一响应

推荐接口分组：

- `ingestion`：文档导入、解析状态查询
- `qa`：问答、引用返回
- `memory`：偏好记忆/知识记忆查询与编辑
- `learning`：新知识对照学习

### 这一层的阅读重点

重点不是看业务写了多少，而是看：

- URL 与请求/响应模型
- 调用了哪个 service 方法
- 是否完整返回来源引用

## 3.2 `service`（业务层）

这是后端的核心层。

典型职责：

- 编排导入流程（解析、切片、向量化、入库）
- 编排问答流程（关键词检索 + 向量检索 + 重排 + 生成）
- 管理三类记忆写入、更新、删除
- 执行“新知识对照旧知识”流程并产出学习卡片
- 保证引用完整性与可追溯性

建议服务划分：

- `IngestionService`
- `QaService`
- `MemoryService`
- `LearningService`

### 这一层的阅读重点

重点看一个业务用例如何拆步：

- 校验输入
- 调用检索与数据层
- 生成结果
- 写回记忆和状态
- 返回引用与元数据

## 3.3 `repository`（数据访问层）

典型职责：

- MySQL 表读写（偏好、知识元数据、反馈、学习卡片）
- 向量库索引写入与召回
- Redis 缓存与短时会话状态
- 外部依赖访问（解析器、Embedding、Rerank、LLM 客户端封装）

这一层关注“怎么存、怎么取、怎么调”，不承担业务流程决策。

## 4. 主要业务域怎么读

## 4.1 `ingestion`：资料导入与知识入库

它是 MVP 的第一优先域。

### 它实现了什么

- 导入原始资料（PDF/Markdown/网页/笔记/聊天记录）
- 文本切片与元数据抽取
- 写入知识片段与向量索引

### 它为什么值得先读

问答质量首先取决于入库质量；切片策略、元数据完整性、引用标注会直接影响召回与可追溯性。

## 4.2 `qa`：检索增强问答

### 它实现了什么

- 混合检索（关键词 + 向量 + 重排）
- 基于证据生成回答
- 返回结构化引用（来源、片段、定位信息）

### 需要注意的点

- 不得只依赖向量相似度
- 不得在缺证据情况下强行回答

## 4.3 `memory`：记忆管理

### 它实现了什么

- 偏好记忆写入与更新（语言偏好、输出长度偏好）
- 会话记忆短时存储与淘汰
- 知识记忆的编辑、删除、追溯查询

### 这个域的特点

它不仅是存储，还要保证主存、索引、缓存一致性。

## 4.4 `learning`：新知识对照旧知识

### 作用

当有新知识进入时，自动生成：

- 已知内容
- 新增信息
- 易混淆点
- 可类比点
- 总结卡片

### 为什么它重要

这是区别于普通 RAG 问答系统的核心能力，直接体现“学习型记忆系统”的价值。

## 5. 典型请求链路怎么走

## 5.1 文档导入链

```text
POST /v1/documents/ingest
  -> IngestionController.ingest
  -> IngestionService.ingest_document
  -> Parser/Chunker
  -> Repository 写 MySQL
  -> Repository 写向量库
  -> Repository 刷新 Redis 状态
```

## 5.2 问答链

```text
POST /v1/qa/ask
  -> QaController.ask
  -> QaService.ask
  -> 混合检索（关键词+向量）
  -> Rerank
  -> LLM 生成
  -> 返回引用与答案
```

## 5.3 新知识对照学习链

```text
POST /v1/learning/contrast
  -> LearningController.contrast
  -> LearningService.generate_contrast_card
  -> 检索旧知识
  -> 生成对照结果
  -> 写回学习卡片与知识关系
```

## 6. 文档体系怎么用

建议文档入口：`docs/README.md`

优先沉淀文档目录：

- `docs/business-flows/ingestion/`
- `docs/business-flows/qa/`
- `docs/business-flows/learning/`
- `docs/data-model/`
- `docs/api/`

你可以把这些文档当成：

- 业务流程说明
- 联调规范补充
- 数据模型与迁移依据

## 7. 测试和架构约束

你需要知道的原则：

- Controller 保持薄，核心规则放 Service
- Repository 不写业务决策，只做数据访问
- 检索、引用、删除一致性变更必须补测试

建议最小测试集：

- 导入后可检索到目标片段
- 回答包含有效引用
- 偏好记忆更新可影响生成风格
- 删除知识后不可继续被召回
- 新知识对照结果包含四类核心字段

## 8. 新人最推荐的阅读顺序

建议按下面顺序：

1. `需求分析.md`
2. `AGENTS.md`
3. `main.py`
4. `controllers/` 下的问答入口
5. `services/` 下的问答流程
6. `repositories/` 下的向量库实现
7. `repositories/` 下的 MySQL 实现
8. `repositories/` 下的 Redis 实现
9. `services/` 下的学习流程
10. `tests/` 中问答与引用相关测试

## 9. 你最容易踩的坑

### 1) 只做向量检索，不做关键词与重排

会导致召回不稳、可解释性差。

### 2) 把业务规则写进 Controller 或 Repository

后续维护成本会迅速上升。

### 3) 忽略引用结构设计

回答看似可用，但无法审计与回溯。

### 4) 删除知识只删主表，不删索引与缓存

会出现“已删除内容仍被召回”的严重问题。

### 5) 把所有历史会话塞进 prompt

成本高、噪声大，还会稀释有效证据。

## 10. 给新人的一句话建议

先把“文档导入 -> 混合检索问答 -> 引用返回”主链跑通，再做偏好记忆和新知识对照学习；主链打稳后，系统扩展会简单很多。

