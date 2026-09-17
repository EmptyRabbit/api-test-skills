# 接口测试用例生成

针对 Java 服务的代码改动，生成可跑通的 pytest 接口用例。分析改动 → 设计场景 → mock/造数 → 生成用例 → 执行修复；每步出 md，**确认后再继续**，不确定会问你。

仓库：<https://github.com/EmptyRabbit/api-test-skills>

任选其一：**Skills**（Cursor / Claude Code）或 **本地网页**。

---

## 用法一：Skills

需要：Cursor 或 Claude Code、本机已有被测 Java 代码、Python 3.8+（跑生成的用例）。数据库 / 配置中心 MCP 可选。

**装插件（推荐）** — 命令带 `api-test:` 前缀。

- Cursor：Customize → Plugins，添加本仓库，安装 `api-test`
- Claude Code：

```bash
/plugin marketplace add EmptyRabbit/api-test-skills
/plugin install api-test@api-test-skills
```

或不走插件（命令无前缀，升级用 `npx skills update`；去掉 `-g` 只装当前项目）：

```bash
npx skills add https://github.com/EmptyRabbit/api-test-skills.git -g -y --agent claude-code cursor
```

有公司适配包则先按其说明安装，再 `npx api-test-skills use <适配包名>`（`--project` 限当前项目；`use none` 关闭；`status` 查看）。不配也能跑，mock 可能跳过。

**开始：** 说「用 api-test:api-generate-api-tests 帮我给这次改动生成接口测试用例」，或斜杠选 `/api-test:api-generate-api-tests`（拷贝安装用 `/api-generate-api-tests`）。

必填：接口名（operation）、Pod IP、本机仓库绝对路径、base / feature 分支、产物目录。  
选填：需求文档、appid、发布环境。缺项会一次性列出。看产物目录 md，不对就改口。用例缺包时按该目录 `requirements.txt` 安装。

---

## 用法二：本地网页

需要：Git（Windows：[Git for Windows](https://git-scm.com/download/win)）、Python 3.11+、Node 18+、已登录的 `claude` CLI。

1. 下载本仓库。
2. 复制 `apps/server/platform.yaml.example` → `apps/server/platform.yaml`（密钥勿提交）。无适配则 `vendor: none`；模型/token 按文件注释填。

在 `apps` 下执行（首次会自动装后端 venv 和前端依赖）：

| | 启动 | 停止 |
|---|---|---|
| Windows | `dev.cmd start` | `dev.cmd stop` |
| Mac / Linux / Git Bash | `./dev.sh start` | `./dev.sh stop` |

另有 `status`、`restart`、`logs server`、`logs web`。就绪后打开 <http://localhost:5173>。

网页：填用户名 → 选模型（Auth Token 可空）→ Git 地址、base（多为 `master`）、feature（可多仓，工作区克隆第一个）→ 写要测什么 → **开始**。聊天里再补接口名、Pod IP 等。提示后端未启动则先 `start` 再刷新。

---

## 写适配（研发）

独立仓 `api-test-skills-<vendor>`，装到 `skills/` 后 `npx api-test-skills use <vendor>`。按需覆盖 `api-prepare-mock-data` / `api-prepare-framework-data` / `api-write-pytest-cases` 的 `-<vendor>` 版。命名必须是 `<核心 skill>-<vendor>`；只补工具细节；专有名词只出现在适配 skill。

下列签名须两仓一致，改时同步并跑 `tests/test_mq_client_core.py` 与适配仓 conformance 测试：

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

自测：`pip install -r skills/api-write-pytest-cases/template/requirements.txt pytest && pytest tests/ && node --test cli/cli.test.js`  
网页开发见 `apps/server/README.md`、`apps/web/README.md`。
