---
name: write-pytest-cases
description: 依据测试场景、mock 方案和框架数据方案，基于 template 模板生成 pytest 接口自动化测试工程与用例代码。当用户要生成接口测试代码、把测试场景落成 pytest 用例时使用。
---

# 生成 pytest 用例

读当前批次的 `03-mock-plan.md`、`04-framework-data.md` 以及全量的 `02-scenarios.md`（只处理
本批次的场景），基于本 skill 目录下的 [template/](template/) 生成用例工程，并产出当前批次的
`05-case-design.md`。

代码风格及详细规则见 [STYLE.md](STYLE.md)，产物结构见 [TEMPLATE.md](TEMPLATE.md)，
红线见 `../generate-api-tests/CONVENTIONS.md`。

## 批次范围

只为**当前批次**的场景生成用例。batch1 只写主流程（冒烟），跑通后才动 batch2。
后续批次往已有文件里追加 test 函数，不要推倒重写；文件顶部 docstring 的
「覆盖场景」和「批次」要一起更新。

产物落到 `docs/batch<N>/05-case-design.md`，状态头的阶段写成 `batch<N>/05-用例设计`。

## 1. 搭工程

把 `template/` 下的 `frame/`、`conftest.py`、`config.yaml`、`requirements.txt`、`.gitignore`
复制到产物目录，按需要用到的能力填 `config.yaml`：DB 连接（用户提供）、Redis 集群名、
appid / 环境 / Pod IP。用不到的配置项删掉，不要留一堆模板占位。

环境常量落到 `tests/env_config.py`（模板里有示例），填成本次被测的真实值。

`logs/` 不用手动建，跑用例时自动生成，已在 `.gitignore` 里忽略。

## 2. 写用例

一个 operation 拆成多个文件，默认按调用链阶段或功能模块拆，场景有清晰需求分组时按需求分组。
文件名走 PEP 8 蛇形，例如 `test_processor_chain_content.py`。单文件超过 8 个 test 函数
或约 150 行就继续拆。拆分与命名细则见 STYLE.md。

单个文件的结构固定为：**文件 docstring → 模块常量 → `_invoke` 请求构造 →
`_assert_xxx` 公共断言 → 各场景 test 函数**。

要点：

- 文件顶部 docstring 写明：所属批次、覆盖场景的业务语义（尾部括号附场景 ID 做追溯，
  不要只写一串裸 ID）、对应改动点、执行前置；
- 环境常量从 `tests/env_config.py` import，业务断言常量写在各自文件内；
- `MOCK_IDS = {场景ID: CaseId}` 放文件顶部，`_invoke` 按场景注入
  mock header（例：`X-Mock-Id`，具体 header 名由 vendor 适配决定）；没有 CaseId 的场景不带该头；
- 每个 test 函数对应一个场景，docstring 分「场景」「步骤」两段：**场景**用一句
  业务语义描述预期结果，尾部括号标注「对应 Sx，改动点 Cy」做追溯，
  **不要把 ID 顶到首行**；**步骤**编号列出跨系统动作（接口调用、DB SQL、
  Redis 函数+参数、MQ 收发），格式与写法见 STYLE.md 的「用例注释」；
- **所有响应断言统一走 jsonpath**（`jsonpath-ng`），禁止 `resp["a"]["b"]` 链式取值；
  通用工具从 `frame.jsonpath_utils` 引入（`jp` / `jp_all` / `assert_jp` / `load_json_field`），
  不要在用例文件里重复定义；遇到 `resultJson` 这类 string 化 JSON 字段用
  `load_json_field` 解开再走 jsonpath，详见 STYLE.md 的「断言：统一走 jsonpath」；
- 需要造数的场景通过 `conftest.py` 的 fixture 拿数据，fixture 在 `yield` 后清理动态数据；
- 仅入参不同的同构场景用 `parametrize` 合并，参数里带场景 ID；
- 业务型 helper（`_invoke`、`_assert_xxx`）只在同文件内两个以上场景复用时才抽，
  **不要跨文件共享**；纯工具型 helper（jsonpath 系列）走 `frame.jsonpath_utils`；
- 不写任何日志代码，也不要 print 报文——请求响应由框架自动落到 `logs/`。

**文件命名速查**（详见 STYLE.md §文件拆分与命名）：

```
tests/
├── env_config.py                      环境常量，唯一的跨文件复用
├── test_processor_chain_entry.py      入口校验
├── test_processor_chain_recall.py     召回与重排
└── test_processor_chain_channel.py    通道投放
```

**请求日志自动落盘**：`HttpClient` 每次调用后自动记录请求与响应，`conftest.py` 的 autouse
fixture 在用例结束后写入 `logs/<用例函数名>.md`。**用例代码无需写任何日志相关代码**，
也不要自己 print 报文。

## 3. 断言纪律

这一条决定用例有没有价值，必须严格执行。

**统一走 jsonpath**：所有响应断言用 `jsonpath-ng`，禁止链式取值。工具函数
`jp` / `jp_all` / `assert_jp` / `load_json_field` 从 `frame.jsonpath_utils` 引入，
不在用例文件里重复实现。string 化的 JSON 字段用 `load_json_field` 解开再走 jsonpath。
写法与更多示例见 STYLE.md。

**字段级完整断言**：`02-scenarios.md` 里写的每一条预期结果都要断到，不允许遗漏。
有副作用的场景补 DB / Redis / MQ 落地断言。

**禁止防御性模糊写法**：

```python
# 禁止：同时接受多种返回，真出问题抓不住
assert selling is True or str(selling).lower() == "true"
value = data.get("cityId") or data.get("cityid")

# 禁止：链式取值，失败信息没有路径
assert resp["data"]["items"][0]["id"] == "A"

# 正确：结构已确定，jsonpath 直接断
assert_jp(resp, "$.hasSellingPoint", True)
assert_jp(resp, "$.cityId", 228)
```

响应结构在分析阶段就该确定（读 DTO + 必要时真实调一次接口）。
到了写代码这一步还拿不准某个字段的类型或大小写，**停下来问用户**，不要用兼容代码糊过去。

## 4. 产出 05-case-design.md

三部分内容：

- **映射表**：场景 ID ↔ 用例文件 ↔ 用例函数名 ↔ 对应改动点。检查本批次每个场景都有用例、
  每个用例都能追溯到改动点，缺的要说明原因；
- **执行前置清单**：跑用例前所有人工动作汇总——`config.yaml` 待填的连接信息、
  待去平台配置的 mock Case、待手动修改的配置项、测完需要还原的内容。
  这份清单直接来自本批次的 `03` 和 `04` 的人工待办，不要漏项；
- **失败先看哪里**：一句话告诉用户日志在 `logs/<用例函数名>.md`，失败先翻它、别只看
  pytest 摘要。不要写成"排障入口""日志位置说明"这种官样标题。
