# 框架工具用法

模板工程位于 `../write-pytest-cases/template/`，`frame/` 下的客户端复制到产物目录后直接可用。

## DB

FAT 或测试环境允许增删改查。

**分析阶段**用数据库查询 MCP（具体名字见 vendor 适配 skill）只读查询表结构和现有数据。

**用例中**用 `db_client` fixture，参数是 `config.yaml` 里 `databases` 下的库名：

```python
@pytest.fixture
def order_data(db_client):
    db = db_client("order_db")
    order_id = "demo_test_10001"
    db.execute(
        "INSERT INTO orders (order_id, status, amount) VALUES (%s, %s, %s)",
        (order_id, "PAID", 100),
    )
    yield order_id
    db.execute("DELETE FROM orders WHERE order_id = %s", (order_id,))
```

`config.yaml` 连接信息由用户提供：

```yaml
databases:
  order_db:
    host: "xxx"
    port: 3306
    user: "xxx"
    password: "xxx"
    database: "order_database"
    charset: "utf8mb4"
```

## Redis

参数是 `config.yaml` 里 `redis` 段的集群名。

```python
@pytest.fixture
def user_cache(redis_client):
    cache = redis_client("main_cache")
    key = "user:10001:profile"
    cache.set(key, {"level": "VIP"}, ex=300)
    yield key
    cache.delete(key)
```

清缓存让新逻辑生效：

```python
cache.delete(f"promotion:{city_id}:list")
```

支持 string / hash / zset：`get` `set` `hset` `hmset` `hget` `hgetall`
`zadd` `zrange` `zrangebyscore` `expire` `delete`。

## 配置中心

**只读查询**用配置中心查询 MCP（具体名字见 vendor 适配 skill）。

**修改**默认由用户人工完成。确需 agent 代改时先征得同意，并在 md 记录原值：

| 文件 | key | 当前值 | 本次需改成 | 测完还原为 |
|---|---|---|---|---|
| feature-flags.json | promoEnabled | false | true | false |

## 消息中间件

核心模板提供 `frame/mq_client.py` 占位。vendor 适配会替换成具体实现。用例中：

```python
MqClient.send(topic="order.paid", data={"orderId": order_id})
```

验证接口发出的消息：

```python
msgs = MqClient.pull(subject="order.paid", group="test-consumer-group", timeout=5000, batch=10)
assert any(m["orderId"] == order_id for m in msgs)
```
