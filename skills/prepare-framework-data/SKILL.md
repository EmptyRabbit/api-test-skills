---
name: prepare-framework-data
description: 为接口测试场景设计 DB、Redis、配置中心、消息中间件四类框架数据的准备方案，查清现状后给出造数代码与人工待办清单。当用户要造测试数据、准备数据库或缓存数据、改配置、发消息验证时使用。
---

# 框架数据准备

读 `01-change-analysis.md` 的依赖清单、`02-scenarios.md`、以及 `03-mock-plan.md` 末尾的
「遗留数据需求」，产出 `04-framework-data.md`。

## 批次范围

只处理**当前批次**的场景。先读 `02-scenarios.md` 的「批次」列，筛出本批次场景，
其余场景一律不碰。

产物落到 `docs/batch<N>/04-framework-data.md`，状态头的阶段写成 `batch<N>/04-框架数据`。

工具用法见 [TOOLS.md](TOOLS.md)，产物结构见 [TEMPLATE.md](TEMPLATE.md)，
红线见 `../generate-api-tests/CONVENTIONS.md`。

## 关于工具

本 skill 只讲**通用方法论**：现状核查、造数与清理、fixture 结构、人工待办清单。
**具体查询工具**（数据库查询 MCP、配置中心查询 MCP、MQ 网关等）由 vendor 适配 skill 提供。

如果本次运行的 vendor 提供了对应适配 skill（`prepare-framework-data-<vendor>`），
主编排会先调本 skill 讲方法论，再调适配 skill 讲工具细节。

## 统一逻辑

每类依赖都走同样三步：**先查清现状 → 再定造数方案 → 落成可执行的 fixture 代码**。

先查现状这一步不能省。不查就造，很容易撞主键、覆盖别人的数据、或者造了一堆
其实环境里本来就有的东西。

## 四类依赖

### DB

- 库名表名优先从代码分析（mapper / XML / DAO），其次用数据库查询工具查，都不行问用户；
- 查表结构和现有数据，确认每个场景需要哪几行、字段值分别是什么；
- 造数走用例里的 `db_client`，写成 pytest fixture；
- **动态构造的数据必须在 `yield` 之后清理，已存在的数据不动**；
- 造数前先查一次，避免主键 / 唯一键冲突；
- 连接信息（host / port / 账号 / 密码）目前拿不到，列进人工待办让用户填 `config.yaml`。

### Redis

- 集群名从代码配置或注入点分析，拿不准问用户；
- 写清 key 格式、value 结构、TTL，用 `redis_client` 在 fixture 中造与清；
- **常见坑**：接口有缓存时，造完 DB 数据要顺手清掉对应缓存 key，否则测不到新逻辑。
  分析时主动检查这一点。

### 配置中心

- 用配置中心查询工具**只读**查出每个 key 的当前值（工具名由 vendor 适配指定）；
- 默认走人工：生成待办表（key / 当前值 / 本次需改成 / 测完还原为），用户手动改完再跑用例；
- 需要 agent 代改时必须先征得用户同意，并把原值记进 md 防止忘记还原；
- 受影响的用例要在文件头注释写明「执行前需确认配置项 X = Y」。

### 消息中间件（MQ）

- 场景需要消息驱动时用 `MqClient.send` 发消息；
- 接口副作用是发消息时，用 `MqClient.pull` 捞出来验证内容；
- MQ 类型与连接方式由 vendor 适配决定，核心模板给的是占位实现。

## 收尾

md 里必须有一份**人工待办清单**，汇总用户要亲自做的事：填 DB 连接信息、
手动改配置中心、以及所有 agent 拿不到的信息。这份清单会被 `write-pytest-cases`
合并进最终的执行前置清单。
