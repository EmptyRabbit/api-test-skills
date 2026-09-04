"""
jsonpath 断言工具。用例统一走这里，禁止 resp["a"]["b"] 链式取值。

规则：
- 单值取用 `jp`，失败信息里带 path，出错时能一眼定位；
- 单值断言用 `assert_jp`；
- 列表匹配用 `jp_all`；
- 响应里塞了 string 化 JSON 的字段（如 `resultJson`）用 `load_json_field` 解出来再走 jsonpath。
"""
import json

from jsonpath_ng.ext import parse


def jp(data, path):
    """按 jsonpath 取第一个匹配值；无匹配抛 AssertionError 让失败信息带上 path。"""
    matches = parse(path).find(data)
    assert matches, f"jsonpath 无匹配：{path}"
    return matches[0].value


def jp_all(data, path):
    """按 jsonpath 返回所有匹配值列表。"""
    return [m.value for m in parse(path).find(data)]


def assert_jp(data, path, expected):
    """按 jsonpath 断言字段等于期望值，失败信息里带 path。"""
    actual = jp(data, path)
    assert actual == expected, f"{path}: 期望 {expected!r}，实际 {actual!r}"


def load_json_field(data, path):
    """取 jsonpath 指向的 string 化 JSON 字段，`json.loads` 后返回对象。"""
    raw = jp(data, path)
    assert isinstance(raw, str) and raw, f"{path}: 期望非空 JSON 字符串"
    return json.loads(raw)
