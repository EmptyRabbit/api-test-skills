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


def test_dump_writes_request_and_response(tmp_path):
    """一次调用要完整落盘：方法、路径、请求头、请求报文、响应报文。"""
    request_log.reset()
    request_log.add(_build_response())

    path = request_log.dump("test_demo", str(tmp_path))

    assert path is not None
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    assert "# 用例 test_demo" in content
    assert "- 请求次数：1" in content
    assert "POST /api/testProcessorChain" in content
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
