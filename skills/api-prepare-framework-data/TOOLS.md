# 框架工具用法

本文件只讲**查现状**和**动作表要写清的事实**。客户端调用代码由消费方写：
接口测试见 `api-write-pytest-cases` 的 STYLE.md「造数动作渲染成 fixture」。

## DB

FAT 或测试环境允许增删改查。

**查现状**用数据库查询 MCP（具体名字见 vendor 适配 skill）只读查询表结构和现有数据。

**动作表**写库名、表名、INSERT/UPDATE/DELETE 的 SQL 和参数。动态插入的行，清理列写对应 DELETE。

连接信息用户事后填进 `config.yaml`，人工待办按这个形状列缺项：

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

**动作表**写集群名、key、操作（SET / DELETE 等）、value、TTL。动态写入的 key，清理列写删除该 key。

接口有缓存时，DB 造数之外另加一行删除对应缓存 key。

## 配置中心

**只读查询**用配置中心查询 MCP（具体名字见 vendor 适配 skill）。

**修改**默认执行方为人工。确需 agent 代改时先征得同意，并在 md 记录原值：

| 文件 | key | 当前值 | 本次需改成 | 测完还原为 |
|---|---|---|---|---|
| feature-flags.json | promoEnabled | false | true | false |

## 消息中间件

**动作表**写 subject、方向（发送 / 拉取验证）、payload 里要出现的字段。
网关地址和缺的参数由 vendor 适配补进行或人工待办。
