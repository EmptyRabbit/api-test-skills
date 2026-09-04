# 用例代码风格

## 语法倾向

用例代码由外包同学长期维护，优先选基础语法。下列写法尽量避免，除非不用它会让代码明显更难懂：

- 闭包工厂（函数里 return 函数）
- 嵌套推导式
- `*args` / `**kwargs`
- 自定义装饰器
- 生成器与 `yield`（fixture 的 `yield` 不算）
- 海象运算符 `:=`
- `getattr` / `setattr` 动态取属性
- `functools` 系列

这是倾向，不是硬性禁令。**不要为了简化而制造重复**：`_invoke`、`_assert_xxx` 这类同文件
helper 继续保留，它们省下的重复远多于增加的跳转成本。`parametrize` 继续可用，但参数里
必须带场景 ID，让失败摘要能直接定位到场景。

`conftest.py` 里 `frame` 客户端的工厂 fixture 写法是既有约定，照用即可，不要改。

## 用例注释

每个 test 函数用 docstring 写清两件事，语言简洁：

1. **场景**：一句话业务描述（含关键条件、预期结果），然后用括号或末尾标记
   对应场景 ID 和改动点，用于追溯 `02-scenarios.md`；
2. **步骤**：编号列出这条用例做了哪些外部动作，每步一行。

**docstring 首句给读的人看，场景 ID 只做追溯**：不要用 `场景：S1 有卖点+有城...`
这种把 ID 顶到最前的写法，读到第一行看不出用例在测什么。改成业务语义前置、
ID 括号收尾：`有卖点+有城（酒店/机票）走完整链并发 PUSH（对应 S1，改动点 C5–C9）`。

步骤只列**跨系统调用**，纯 Python 计算和内部 helper 不写。写法约定：

- 调接口：`调用 POST api/xxx，断言 errorCode=xxx`
- 操 DB：`DB：INSERT INTO ...（具体 SQL 或伪 SQL）`
- 操 Redis：`Redis：set("key", "val") / hgetall("hash")`（函数名 + 参数）
- 发 MQ：`MQ：发送 topic=xxx，模拟 xxx 事件`（**只写场景语义，不写消息报文**）
- 收 MQ：`MQ：拉取 subject=xxx group=xxx`
- 断言中间结果：`断言 xxx`

例子：

```python
def test_paid_order_notified(http_client, paid_order):
    """
    已支付订单触发通知，落库状态更新并发出 order.notified 消息（对应 S3，改动点 C2）。

    步骤：
    1. DB：INSERT orders(id=paid_order, status='PAID')（fixture 已完成）；
    2. 调用 POST api/orderNotify，断言 success=True 且 orderStatus='NOTIFIED'；
    3. MQ：拉取 subject=order.notified group=test-consumer-group，断言存在 orderId=paid_order 的消息。
    """
    resp = _invoke_query(http_client, paid_order)
    assert_jp(resp, "$.success", True)
    assert_jp(resp, "$.orderStatus", "NOTIFIED")

    msgs = MqClient.pull(subject="order.notified", group="test-consumer-group", timeout=5000, batch=10)
    assert any(m["orderId"] == paid_order for m in msgs)
```

parametrize 合并的用例 docstring 一句话讲清共性行为，尾部列出覆盖的场景 ID：

```python
@pytest.mark.parametrize(
    "scenario_id, prd_type",
    [("S1", "F"), ("S2", "H"), ("S3", "OTHER")],
)
def test_selling_point_with_city(http_client, scenario_id, prd_type):
    """
    有卖点+有城市按品类召回（对应 S1/S2/S3，改动点 C1）。

    步骤：
    1. 调用 POST api/testProcessorChain（scenario=T0_INSTALL, cityId=228）；
    2. 断言 resultJson.recallContext.candidate.prdType=参数 prd_type、cityId=228。
    """
    resp = _invoke(http_client, scenario_id, cid=CIDS[scenario_id], city_id=228)
    _assert_candidate(resp, prd_type, 228)
```

## 断言：统一走 jsonpath

用例中所有响应断言一律使用 `jsonpath-ng`，不允许再用 `resp["a"]["b"]` 这种链式取值。
理由：路径字符串化后，失败信息里直接带 path，排障时一眼定位；同时避免 `KeyError` 反复
兜底。

**通用工具函数从 `frame.jsonpath_utils` 引入，不要在每个用例文件里各自定义一份**：

```python
from frame.jsonpath_utils import jp, jp_all, assert_jp, load_json_field
```

四个函数的语义：

- `jp(data, path)`：按 jsonpath 取第一个匹配值，无匹配抛 AssertionError 带上 path；
- `jp_all(data, path)`：返回所有匹配值列表；
- `assert_jp(data, path, expected)`：等值断言，失败信息里带 path；
- `load_json_field(data, path)`：取 jsonpath 指向的 string 化 JSON 字段并 `json.loads`。

业务型 helper（`_invoke`、`_assert_content_ready`、`_assert_creative` 之类和具体
operation 强绑定的）仍然就地定义、不跨文件共享——它们抽出来收益低、跳转成本高。

### 处理 string 化的 JSON 字段

HTTP 响应经常把子结构塞在一个 string 字段里（如 `resultJson`）。用
`load_json_field` 解出来当独立对象，再走 jsonpath，不要试图在 jsonpath 里
跨字符串边界：

```python
from frame.jsonpath_utils import jp, assert_jp, load_json_field

resp = _invoke(http_client, "S1", cid="10001", city_id=228)

# 外层直接断
assert_jp(resp, "$.success", False)
assert_jp(resp, "$.errorCode", "20011")

# resultJson 是 string，先解出来再断
result = load_json_field(resp, "$.resultJson")
assert_jp(result, "$.request.recallContext.candidate.prdType", "F")
assert_jp(result, "$.request.recallContext.candidate.cityId", 228)
assert_jp(result, "$.request.recallContext.candidate.hasSellingPoint", True)
```

### 常用写法

```python
# 单值断言
assert_jp(resp, "$.data.orderId", "N123")

# 列表长度
assert len(jp_all(resp, "$.data.items[*]")) == 3

# 存在性（无匹配即失败）
jp(resp, "$.data.token")

# 条件过滤
paid = jp_all(resp, "$.data.items[?(@.status=='PAID')].id")
assert paid == ["A", "B"]

# 断言不存在
from jsonpath_ng.ext import parse
assert not parse("$.data.legacyField").find(resp)
```

### 禁止

```python
# 禁止：链式取值，失败信息只有 KeyError，看不出哪条路径挂了
assert resp["data"]["items"][0]["id"] == "A"

# 禁止：既 jsonpath 又直接 get，风格混乱
resp["success"]           # ← 用 assert_jp

# 禁止：在用例文件里重复定义 _jp / _assert_jp / _jp_all
# 统一从 frame.jsonpath_utils 引入
```

## 文件骨架

```python
"""
HTTP api/testProcessorChain / T0_INSTALL 场景。

对应改动点：C1（cityId 为空走兜底逻辑）

执行前置：
- 配置项 t0-install-abt-config.json 的 abtEnabled 需为 false
- mock CASE-01 / CASE-02 需已在平台配置完成
"""
import json

from frame.jsonpath_utils import jp, assert_jp, load_json_field
from tests.env_config import APP_ID, ENV_NAME, OPERATION, POD_IP

CHANNEL_DISABLED_CODE = "20011"
INVALID_PARAM_CODE = "20006"

MOCK_IDS = {
    "S1": "56032635",
    "S2": "56034029",
}


def _invoke(http_client, scenario_id, cid, city_id=None):
    """按场景发起请求，自动注入 mock 头。"""
    client = http_client(base_url=f"http://{POD_IP}:8080")
    headers = {}
    if MOCK_IDS.get(scenario_id):
        headers["X-Mock-Id"] = MOCK_IDS[scenario_id]  # 实际 header 名由 vendor 适配决定

    user_context = {"cid": cid, "uid": UID, "locale": LOCALE}
    if city_id is not None:
        user_context["cityId"] = city_id

    return client.post(
        OPERATION,
        params={
            "scenario": "T0_INSTALL",
            "requestId": f"demo-{scenario_id}",
            "userContextJson": json.dumps(user_context, separators=(",", ":")),
        },
        headers=headers,
    )


def _assert_candidate(resp, prd_type, city_id):
    """通道未配置时整链返回 20011，但召回结果仍应写入 resultJson。"""
    assert_jp(resp, "$.success", False)
    assert_jp(resp, "$.errorCode", CHANNEL_DISABLED_CODE)

    result = load_json_field(resp, "$.resultJson")
    assert_jp(result, "$.request.recallContext.candidate.prdType", prd_type)
    assert_jp(result, "$.request.recallContext.candidate.cityId", city_id)
    assert_jp(result, "$.request.recallContext.candidate.hasSellingPoint", True)


def test_sp_flight_with_city(http_client):
    """
    有卖点+有城市+机票，召回机票候选（对应 S1，改动点 C1）。

    步骤：
    1. 调用 POST api/testProcessorChain（scenario=T0_INSTALL, cityId=228，注入 mock CASE-01）；
    2. 断言 resultJson.recallContext.candidate.prdType='F'、cityId=228、hasSellingPoint=True。
    """
    resp = _invoke(http_client, "S1", cid="10001", city_id=228)
    _assert_candidate(resp, "F", 228)


def test_cid_empty(http_client):
    """
    cid 为空时入口校验失败，不进 Dispatcher（对应 S5，改动点 C1）。无需 mock。

    步骤：
    1. 调用 POST api/testProcessorChain（cid=''）；
    2. 断言 success=False、errorCode='20006'、errorMessage 含 'cid'。
    """
    resp = _invoke(http_client, "S5", cid="")
    assert_jp(resp, "$.success", False)
    assert_jp(resp, "$.errorCode", INVALID_PARAM_CODE)
    assert "cid" in jp(resp, "$.errorMessage")
```

## 带造数 fixture 的用例

fixture 写在 `conftest.py`，用例直接声明依赖；docstring 里步骤要提到 fixture 造了什么数据：

```python
def test_paid_order_notified(http_client, paid_order):
    """
    已支付订单触发通知，落库状态更新并发出 order.notified 消息（对应 S3，改动点 C2）。

    步骤：
    1. DB：INSERT orders(id=paid_order, status='PAID')（fixture 已完成）；
    2. 调用 POST api/orderNotify（orderId=paid_order）；
    3. 断言 success=True、orderStatus='NOTIFIED'；
    4. MQ：拉取 subject=order.notified group=test-consumer-group，断言存在 orderId=paid_order 的消息。
    """
    resp = _invoke_query(http_client, order_id=paid_order)
    assert_jp(resp, "$.success", True)
    assert_jp(resp, "$.orderStatus", "NOTIFIED")

    msgs = MqClient.pull(subject="order.notified", group="test-consumer-group", timeout=5000, batch=10)
    assert any(m["orderId"] == paid_order for m in msgs)
```

## parametrize 合并同构场景

只有入参不同、断言逻辑一致时才合并，合并后 docstring 用一句业务语义描述共性，
尾部括号列出覆盖的场景 ID：

```python
@pytest.mark.parametrize(
    "scenario_id, prd_type",
    [("S1", "F"), ("S2", "H"), ("S3", "OTHER")],
)
def test_selling_point_with_city(http_client, scenario_id, prd_type):
    """
    有卖点+有城市按品类召回（对应 S1/S2/S3，改动点 C1）。

    步骤：
    1. 调用 POST api/testProcessorChain（scenario=T0_INSTALL, cityId=228, cid=CIDS[scenario_id]）；
    2. 断言 resultJson.recallContext.candidate.prdType=参数 prd_type、cityId=228。
    """
    resp = _invoke(http_client, scenario_id, cid=CIDS[scenario_id], city_id=228)
    _assert_candidate(resp, prd_type, 228)
```

## 文件拆分与命名

一个 operation 拆成多个用例文件，默认按调用链阶段或功能模块拆；场景本身有清晰的需求分组时
按需求分组拆。判断标准是结构清晰、少复用，不要机械套规则。

文件名走 PEP 8 蛇形命名，operation 名转蛇形后加分组后缀：

```
tests/
├── env_config.py                      环境常量，唯一的跨文件复用
├── test_processor_chain_entry.py      入口校验
├── test_processor_chain_gray.py       实验分流
├── test_processor_chain_recall.py     召回与重排
├── test_processor_chain_content.py    内容渲染
└── test_processor_chain_channel.py    通道投放
```

单文件超过 8 个 test 函数或约 150 行就继续拆。

每个文件顶部 docstring 必须写清四件事，其中「覆盖场景」用一句业务语义描述并附上
场景 ID 做追溯，不要只留一串裸 ID：

```python
"""
HTTP api/testProcessorChain / 内容渲染阶段。

批次：batch1（主流程）
覆盖场景：有卖点+有城完整链、有卖点+无城酒店链、模板降级兜底（对应 S8/S9/S10）
对应改动点：C9、C11、C12

执行前置：
- mock CaseId 见 MOCK_IDS，需先在平台配置
- 配置项 t0-install-abt-config.json 的 abtEnabled 需为 true
"""
```

环境常量统一放 `tests/env_config.py`，这是**唯一**允许的跨文件复用——Pod IP 变更是高频事件，
散落在多个文件里必然漏改：

```python
from tests.env_config import APP_ID, ENV_NAME, OPERATION, POD_IP
```

业务断言常量（错误码、模板 ID、期望文案）留在各自文件内，不集中。

## 请求日志

用例发出的每次 HTTP 请求与响应会自动落盘到 `logs/<用例函数名>.md`，
由 `frame/http_client.py` 和 `conftest.py` 的 autouse fixture 完成。
**用例代码不需要写任何日志相关代码**，也不要自己 print 报文。

具体来说：`HttpClient.get` 和 `HttpClient.post` 在每次调用后自动记录请求与响应；
`conftest.py` 里的 `log_requests` fixture 是 autouse，在每个用例结束后（包括失败时）把记录
写到 `<rootdir>/logs/<sanitized-test-name>.md`。

日志文件名来自 `request.node.name`，所以 `parametrize` 用例的文件名里会带上参数值，
例如 `test_selling_point_with_city[S1-F].md`。这是正常现象，不同参数组合各有独立日志。

## 反面写法

```python
# 反例 1：模糊断言，几种返回都能过，抓不到 bug
assert_jp(resp, "$.selling", True)   # 正
assert selling is True or str(selling).lower() == "true"   # 反

# 反例 2：字段名兜底查找，掩盖真实结构
value = data.get("cityId") or data.get("cityid") or data.get("CityId")

# 反例 3：只断一个字段就收工，场景里写的其他预期全丢了
assert_jp(resp, "$.success", False)

# 反例 4：为了让用例变绿放宽断言
assert jp(resp, "$.errorCode") in ("20011", "20010", "50000")

# 反例 5：绕开 jsonpath 直接链式取值
assert resp["data"]["items"][0]["id"] == "A"

# 反例 6：docstring 首行用「场景：S1 ...」把 ID 顶到最前，读第一行看不出在测什么
# 应改为业务语义前置、ID 括号收尾：「有卖点+有城... （对应 S1，改动点 C1）」
```

反例 4 尤其危险：如果实际返回和预期不符，那是发现了问题，应该停下来报告，
而不是把预期改成实际。
