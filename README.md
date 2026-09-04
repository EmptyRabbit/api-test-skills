# Java 接口测试用例生成 Skills

针对 Java 服务的代码改动，生成能真实跑通的 pytest 接口自动化测试用例。

全流程人机协同：分析改动 → 设计场景 → 造 mock 和框架数据 → 生成用例 → 执行修复，
每个阶段产出一份 md，停下来等你确认后才继续。**所有不确定的信息都会问你，不会猜。**

## 定位

本仓库是**核心通用方法论**：任何公司的 Java 服务都能用，只讲「该分析什么、
该断言什么、造数逻辑该长什么样」。

具体环境相关的工具用法（mock 平台接入、数据库/配置中心/APM 的 MCP 名称、
消息中间件类型）由**独立的 vendor 适配包**提供，通过 `~/.api-test-skills.yaml`
的 `vendor:` 字段加载。核心仓库不带任何公司专有信息。

## 安装

```bash
npx skills add https://github.com/<org>/api-test-skills.git -g -y --agent claude-code cursor
```

只装到当前项目：去掉 `-g`。之后升级：

```bash
npx skills update
```

装了 vendor 适配包后，写一份配置（一次配置，永久生效）：

```bash
npx api-test-skills use <vendor-name>
```

只对当前项目生效：

```bash
npx api-test-skills use <vendor-name> --project
```

关闭适配：`npx api-test-skills use none`。查看当前生效的 vendor 及来源：
`npx api-test-skills status`。

`<vendor-name>` 是已安装的适配包名。不配置就是纯核心模式，跑得起来但阶段 3（mock）
默认跳过——外部依赖走真实调用。

项目根的 `.api-test-skills.yaml` 优先于 `~/.api-test-skills.yaml`。

## 前置条件

**两个 MCP**（在 Cursor / Claude Code 里配置）——具体 MCP 名称由 vendor 适配指定：

| MCP | 缺了会怎样 |
|---|---|
| 数据库查询 MCP | 库表信息只能靠代码分析和问你 |
| 配置中心查询 MCP | 配置值只能问你 |

**Python 环境**：生成的用例工程需要 python 3.8+，依赖见
`skills/write-pytest-cases/template/requirements.txt`。**环境由你自己装**，skill 只检查不代劳。

## 怎么用

在装了 skill 的工作区里说一句：

> 用 generate-api-tests 帮我给这次改动生成接口测试用例

然后按提示提供必要信息：

- 被测接口名（operation）
- 发布环境
- Pod IP（直连指定实例）
- 代码仓库本地路径
- base / feature 分支
- 产物目录
- 相关 PRD / 设计文档（可选）
- appid（vendor 有应用编号体系时必填）

必填项没提供或值明显不对时会一次性列出让你补齐，不会边猜边跑。

## 为你的公司添加适配

参照下面的结构写一份 `api-test-skills-<yourvendor>` 独立仓库，装到 `skills/` 根下，
再执行 `npx api-test-skills use <yourvendor>` 即可。

按需覆盖以下三个核心 skill 的适配层：

- `prepare-mock-data-<vendor>` —— 讲你们 mock 平台的接入方式（怎么触发 mock、
  怎么配 CaseId、mock header 用什么名字）
- `prepare-framework-data-<vendor>` —— 讲具体的数据库查询 / 配置中心查询工具用法、
  MQ 连接方式
- `write-pytest-cases-<vendor>` —— 补齐 `frame/` 里 vendor 特定客户端的实现
  （如自研的 SOA/RPC client、消息中间件 client、Redis 主从分离 client）

关键约定：

- 适配 skill 名必须是 `<核心 skill 名>-<vendor>` 形式；
- 适配 skill 只补充工具细节，产物 md 结构由核心 skill 定，不要另起炉灶；
- vendor 专有用词（公司名、内部平台名、内部工具名）只允许出现在 `-<vendor>`
  后缀的 skill 里，核心仓库保持中性。

### 已知的 vendor 适配

- 携程内部有独立的 `api-test-skills-ctrip` 适配包（内网仓库，非公开）。

## 接口契约（跨仓库对齐点）

以下签名由核心仓库定义，vendor 适配层的 overlay 版**必须保持一致**——用户工程从
核心 skill md 抄的示例代码要在装了适配层后依然能跑：

```python
# frame/mq_client.py
class MqClient:
    @classmethod
    def send(cls, topic: str, data: dict, **kwargs) -> dict: ...
    @classmethod
    def pull(cls, subject: str, group: str, timeout: int, batch: int, **kwargs) -> list: ...

# frame/redis_client.py
class RedisClient:
    def __init__(self, cluster_name: str, read_master: bool = False) -> None: ...
    # get / set / zadd / zrange / zrangebyscore / hset / hmset / hget / hgetall / expire / delete
```

改任一签名必须**两仓同步**，并同步 `tests/test_mq_client_core.py`（本仓库）与
适配层各自的 conformance 测试。

## 本地测试

```bash
pip install -r skills/write-pytest-cases/template/requirements.txt pytest
pytest tests/
node --test cli/cli.test.js
```

Python 测试全部离线，验证 request_log / http_client 日志钩子 / MqClient 占位契约 / config 重载。
Node 测试验证 `npx api-test-skills` 写配置与 status 优先级。
