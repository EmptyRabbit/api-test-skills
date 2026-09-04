"""
用例请求日志：把用例发出的 HTTP 请求与响应落成 md，方便排障和复现。

记录由 frame/http_client.py 自动写入，conftest.py 的 autouse fixture 负责清空与落盘。
用例代码不需要调用本模块。
"""
import json
import os
import time

# 进程内模块级列表；pytest-xdist 并行时各 worker 独立，不共享记录。
_records = []


def reset():
    """用例开始前清空上一条用例的记录。"""
    del _records[:]


def add(resp):
    """记录一次请求与响应。resp 是 httpx 的 Response 对象。"""
    request = resp.request
    try:
        elapsed = "%.3fs" % resp.elapsed.total_seconds()
    except Exception:
        # 手工构造的 httpx.Response 访问 elapsed 会抛 RuntimeError，日志写入不能因此失败。
        elapsed = "未知"

    _records.append({
        "method": request.method,
        "path": request.url.path,
        "url": str(request.url),
        "headers": dict(request.headers),
        "body": _decode(request.content),
        "status_code": resp.status_code,
        "response": resp.text,
        "elapsed": elapsed,
    })


def dump(case_name, log_dir):
    """把当前用例的记录写成 <log_dir>/<用例名>.md。没有记录时不生成文件。"""
    if not _records:
        return None

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    path = os.path.join(log_dir, _safe_name(case_name) + ".md")

    lines = []
    lines.append("# 用例 " + case_name)
    lines.append("")
    lines.append("- 执行时间：" + time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("- 请求次数：" + str(len(_records)))
    lines.append("")

    index = 1
    for item in _records:
        lines.append("## 请求 %d · %s %s" % (index, item["method"], item["path"]))
        lines.append("")
        lines.append("- URL：" + item["url"])
        lines.append("- 状态码：" + str(item["status_code"]))
        lines.append("- 耗时：" + item["elapsed"])
        lines.append("")
        lines.append("### 请求头")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(item["headers"], ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
        lines.append("### 请求报文")
        lines.append("")
        lines.append("```json")
        lines.append(_pretty(item["body"]))
        lines.append("```")
        lines.append("")
        lines.append("### 响应报文")
        lines.append("")
        lines.append("```json")
        lines.append(_pretty(item["response"]))
        lines.append("```")
        lines.append("")
        index = index + 1

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    return path


def _decode(content):
    if not content:
        return ""
    return content.decode("utf-8", errors="replace")


def _pretty(text):
    """能解析成 JSON 就格式化，否则原样输出。"""
    if not text:
        return "（空）"
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except ValueError:
        return text


def _safe_name(case_name):
    """把用例名里 Windows 文件名不允许的字符换成下划线。"""
    safe = case_name
    for char in '[]/\\:*?"<>|':
        safe = safe.replace(char, "_")
    return safe
