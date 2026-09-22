"""
用例操作日志：把用例里各客户端调用按顺序落成 md，方便排障和复现。

HTTP 由 frame/http_client.py 在拿到响应后写入；DB / Redis / MQ 等通过
logged() 装饰器自动写入。conftest.py 的 autouse fixture 负责清空与落盘。
用例代码不需要调用本模块。
"""
import functools
import inspect
import json
import os
import time

# 进程内模块级列表；pytest-xdist 并行时各 worker 独立，不共享记录。
_records = []


def reset():
    """用例开始前清空上一条用例的记录。"""
    del _records[:]


def add_op(kind, action, params, result=None, error=None, elapsed=None):
    """追加一条操作记录。kind 自由字符串，dump 时只做大写展示。"""
    record = {
        "kind": kind,
        "action": action,
        "params": params if params is not None else {},
        "elapsed": elapsed if elapsed is not None else "未知",
    }
    if error is not None:
        record["result"] = {"error": error}
    else:
        record["result"] = result
    _records.append(record)


def add(resp):
    """记录一次 HTTP 请求与响应。resp 是 httpx 的 Response 对象。"""
    request = resp.request
    try:
        elapsed = "%.3fs" % resp.elapsed.total_seconds()
    except Exception:
        # 手工构造的 httpx.Response 访问 elapsed 会抛 RuntimeError，日志写入不能因此失败。
        elapsed = "未知"

    add_op(
        "http",
        request.method,
        {
            "method": request.method,
            "path": request.url.path,
            "url": str(request.url),
            "headers": dict(request.headers),
            "body": _maybe_json(_decode(request.content)),
        },
        result={
            "status_code": resp.status_code,
            "body": _maybe_json(resp.text),
        },
        elapsed=elapsed,
    )


def logged(kind):
    """装饰客户端公开方法：按调用顺序记下传参和返回值（或异常信息）。"""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            params = _bound_params(fn, args, kwargs)
            _attach_client_identity(args, params)
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                _safe_add_op(
                    kind,
                    fn.__name__,
                    params,
                    error=str(exc),
                    elapsed="%.3fs" % (time.perf_counter() - start),
                )
                raise
            _safe_add_op(
                kind,
                fn.__name__,
                params,
                result=_jsonable(result),
                elapsed="%.3fs" % (time.perf_counter() - start),
            )
            return result

        return wrapper

    return decorator


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
    lines.append("- 操作次数：" + str(len(_records)))
    lines.append("")

    index = 1
    for item in _records:
        lines.append("## %d · %s" % (index, _heading(item)))
        lines.append("")
        lines.append("- 耗时：" + item["elapsed"])
        lines.append("")
        lines.append("### 传参")
        lines.append("")
        lines.append("```json")
        lines.append(_pretty(item.get("params")))
        lines.append("```")
        lines.append("")
        lines.append("### 结果")
        lines.append("")
        lines.append("```json")
        lines.append(_pretty(item.get("result")))
        lines.append("```")
        lines.append("")
        index = index + 1

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    return path


def _safe_add_op(kind, action, params, result=None, error=None, elapsed=None):
    try:
        add_op(kind, action, params, result=result, error=error, elapsed=elapsed)
    except Exception:
        pass


def _bound_params(fn, args, kwargs):
    try:
        sig = inspect.signature(fn)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
    except (TypeError, ValueError):
        return {"args": _jsonable(args[1:]), "kwargs": _jsonable(kwargs)}

    data = {}
    for name, value in bound.arguments.items():
        if name in ("self", "cls"):
            continue
        param = sig.parameters.get(name)
        if param is not None and param.kind == inspect.Parameter.VAR_KEYWORD:
            for key, item in value.items():
                data[key] = _jsonable(item)
            continue
        data[name] = _jsonable(value)
    return data


def _attach_client_identity(args, params):
    if not args:
        return
    inst = args[0]
    db_name = getattr(inst, "db_name", None)
    if db_name is not None:
        params.setdefault("db_name", db_name)
    cluster_name = getattr(inst, "cluster_name", None)
    if cluster_name is not None:
        params.setdefault("cluster_name", cluster_name)


def _heading(item):
    kind = (item.get("kind") or "op").upper()
    action = item.get("action") or ""
    params = item.get("params") or {}
    if (item.get("kind") or "").lower() == "http":
        method = params.get("method") or action
        path = params.get("path") or ""
        return ("HTTP %s %s" % (method, path)).strip()
    return ("%s %s" % (kind, action)).strip()


def _jsonable(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


def _maybe_json(text):
    if not text:
        return ""
    try:
        return json.loads(text)
    except ValueError:
        return text


def _decode(content):
    if not content:
        return ""
    return content.decode("utf-8", errors="replace")


def _pretty(value):
    """能转成 JSON 就格式化，否则原样输出。"""
    if value is None or value == "":
        return "（空）"
    if isinstance(value, str):
        try:
            return json.dumps(json.loads(value), ensure_ascii=False, indent=2)
        except ValueError:
            return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except TypeError:
        return str(value)


def _safe_name(case_name):
    """把用例名里 Windows 文件名不允许的字符换成下划线。"""
    safe = case_name
    for char in '[]/\\:*?"<>|':
        safe = safe.replace(char, "_")
    return safe
