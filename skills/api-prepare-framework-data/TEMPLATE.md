# 04-framework-data.md 模板

```markdown
> 阶段：batch1/04-框架数据
> 状态：待确认
> 上游：batch1/02-scenarios.md、03-mock-plan.md
> 更新时间：YYYY-MM-DD HH:MM

**一句话结论**：本批只有 S3 需要造数——DB 插一条 PAID 订单、发一条 order.paid 消息；
S1 需要人工清一次 Redis 缓存。动作已写清，等你填好 `config.yaml` 里的库连接信息。

# 框架数据准备方案

本文件只覆盖 batch1 的场景。动作与测试框架无关，下游照表渲染成用例步骤。

## 一、按场景的数据需求

| 场景 | DB | Redis | 配置中心 | 消息中间件 |
|---|---|---|---|---|
| S1 | 无 | 需清 promotion 缓存 | abtEnabled=false | 无 |
| S3 | orders 造 1 条 PAID 记录 | 无 | 无 | 前置发 order.paid |

## 二、DB

### 现状核查

- 库 `order_database`、表 `orders`，主键 `order_id`；
- 查过 `order_id='demo_test_10001'` 不存在，可以直接插入，不会撞现有数据。

### 造数动作

| 场景 | 目标 | 操作 | 数据 | 清理 | 执行方 |
|---|---|---|---|---|---|
| S3 | order_database.orders | INSERT | order_id=demo_test_10001, status=PAID, amount=100 | DELETE order_id=demo_test_10001 | 自动 |

```sql
INSERT INTO orders (order_id, status, amount) VALUES ('demo_test_10001', 'PAID', 100);
-- 清理
DELETE FROM orders WHERE order_id = 'demo_test_10001';
```

## 三、Redis

| 场景 | 目标 | 操作 | 数据 | 清理 | 执行方 |
|---|---|---|---|---|---|
| S1 | 集群 main_cache，key `promotion:228:list` | DELETE | 无 | 无（只清缓存） | 自动 |

这条接口有缓存，不清就会命中旧值，测不到新逻辑。

## 四、配置中心（人工修改）

| 场景 | 目标 | 操作 | 数据 | 清理 | 执行方 |
|---|---|---|---|---|---|
| S1、S2 | t0-install-abt-config.json / abtEnabled | 确认当前值 | 当前 false，本次保持 false | 无需还原 | 人工 |

## 五、消息中间件

| 场景 | 目标 | 操作 | 数据 | 清理 | 执行方 |
|---|---|---|---|---|---|
| S3 | subject `order.paid` | 发送 | payload 含 orderId=demo_test_10001 | 无 | 自动 |
| S3 | subject `order.notified` | 拉取验证 | 存在 orderId=demo_test_10001 | 无 | 自动 |

## 六、人工待办清单

- [ ] 在 `config.yaml` 填写 order_db 连接信息（host / port / user / password / database）
- [ ] 确认配置项 `t0-install-abt-config.json` 的 `abtEnabled` 当前为 false

## 七、存疑点

- [ ] promotion 缓存的 key 格式是否含 locale 后缀，代码里没看明确。
```
