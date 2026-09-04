# 04-framework-data.md 模板

```markdown
> 阶段：batch1/04-框架数据
> 状态：待确认
> 上游：02-scenarios.md、03-mock-plan.md
> 更新时间：YYYY-MM-DD HH:MM

# 框架数据准备方案

本文件只覆盖 batch1 的场景。

## 一、按场景的数据需求

| 场景 | DB | Redis | 配置中心 | 消息中间件 |
|---|---|---|---|---|
| S1 | 无 | 需清 promotion 缓存 | abtEnabled=false | 无 |
| S3 | orders 造 1 条 PAID 记录 | 无 | 无 | 前置发 order.paid |

## 二、DB

### 现状核查

- 库 `order_database`、表 `orders`，主键 `order_id`；
- 查过 `order_id='demo_test_10001'` 不存在，可以直接插入，不会撞现有数据。

### 造数方案

| 场景 | 表 | 操作 | 数据 | 清理 |
|---|---|---|---|---|
| S3 | orders | INSERT | order_id=demo_test_10001, status=PAID, amount=100 | 用例结束 DELETE |

### fixture 代码

```python
@pytest.fixture
def paid_order(db_client):
    db = db_client("order_db")
    order_id = "demo_test_10001"
    db.execute("INSERT INTO orders (order_id, status, amount) VALUES (%s, %s, %s)",
               (order_id, "PAID", 100))
    yield order_id
    db.execute("DELETE FROM orders WHERE order_id = %s", (order_id,))
```

## 三、Redis

| 场景 | 集群 | key | 操作 | 说明 |
|---|---|---|---|---|
| S1 | main_cache | promotion:228:list | 用例前删除 | 这条接口有缓存，不清缓存就会命中旧值，测不到新逻辑 |

## 四、配置中心（人工修改）

| 文件 | key | 当前值 | 本次需改成 | 测完还原为 | 影响场景 |
|---|---|---|---|---|---|
| t0-install-abt-config.json | abtEnabled | false | false | 无需还原 | S1、S2 |

## 五、消息中间件

| 场景 | subject | 方向 | 说明 |
|---|---|---|---|
| S3 | order.paid | 发送 | 前置驱动，用 MqClient.send |
| S3 | order.notified | 拉取验证 | 接口副作用，用 MqClient.pull 校验内容 |

## 六、人工待办清单

- [ ] 在 `config.yaml` 填写 order_db 连接信息（host / port / user / password / database）
- [ ] 确认配置项 `t0-install-abt-config.json` 的 `abtEnabled` 当前为 false

## 七、存疑点

- [ ] promotion 缓存的 key 格式是否含 locale 后缀，代码里没看明确。
```
