"""frame/request_log.py 的验证测试。全程离线，不依赖网络与真实环境。"""
import os

import httpx

from frame import request_log


def _build_response():
    """构造一个带完整 request 的 httpx 响应，模拟一次被测接口调用。"""
    request = httpx.Request(
        "POST",
        "http://10.1.2.3:8080/api/testProcessorChain",
        json={"scenario": "T0_INSTALL"},
        headers={"X-Mock-Id": "56032635"},
    )
    return httpx.Response(
        200,
        json={"success": False, "errorCode": "20005"},
        request=request,
    )


def test_dump_writes_params_and_result(tmp_path):
    """一次调用要完整落盘：传参与结果，不再写「原始命令」专段。"""
    request_log.reset()
    request_log.add(_build_response())

    path = request_log.dump("test_demo", str(tmp_path))

    assert path is not None
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    assert "# 用例 test_demo" in content
    assert "- 操作次数：1" in content
    assert "### 传参" in content
    assert "### 结果" in content
    assert "POST" in content
    assert "/api/testProcessorChain" in content
    assert "56032635" in content
    assert '"scenario": "T0_INSTALL"' in content
    assert '"errorCode": "20005"' in content


def test_elapsed_unavailable_is_tolerated(tmp_path):
    """手工构造的响应没有 elapsed，访问会抛异常，不能让日志写不出来。"""
    request_log.reset()
    request_log.add(_build_response())

    path = request_log.dump("test_demo", str(tmp_path))

    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    assert "- 耗时：未知" in content


def test_reset_clears_previous_records(tmp_path):
    """上一条用例的记录不能漏进下一条用例。"""
    request_log.reset()
    request_log.add(_build_response())
    request_log.reset()

    assert request_log.dump("test_demo", str(tmp_path)) is None


def test_case_name_with_brackets_is_sanitized(tmp_path):
    """parametrize 用例名带中括号，直接当文件名在 Windows 上不可靠。"""
    request_log.reset()
    request_log.add(_build_response())

    path = request_log.dump("test_demo[S8-F-11985]", str(tmp_path))

    assert os.path.basename(path) == "test_demo_S8-F-11985_.md"


def test_add_op_keeps_call_order(tmp_path):
    """不同类型操作按 append 顺序编号，方便对照用例步骤。"""
    request_log.reset()
    request_log.add_op("db", "query", {"sql": "SELECT 1", "params": None}, result=[{"n": 1}])
    request_log.add(_build_response())
    request_log.add_op("redis", "get", {"key": "foo"}, result="bar")

    path = request_log.dump("test_order", str(tmp_path))
    with open(path, encoding="utf-8") as handle:
        content = handle.read()

    db_at = content.index("## 1 · DB query")
    http_at = content.index("## 2 · HTTP POST")
    redis_at = content.index("## 3 · REDIS get")
    assert db_at < http_at < redis_at
    assert "- 操作次数：3" in content
    assert "SELECT 1" in content
    assert '"key": "foo"' in content
    assert '"bar"' in content or "bar" in content


def test_add_op_records_error_instead_of_result(tmp_path):
    """调用失败时仍要留下传参和错误信息。"""
    request_log.reset()
    request_log.add_op("mq", "send", {"topic": "order.paid"}, error="MqClient.send 未实现")

    path = request_log.dump("test_error", str(tmp_path))
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    assert "### 传参" in content
    assert "order.paid" in content
    assert "### 结果" in content
    assert "未实现" in content
