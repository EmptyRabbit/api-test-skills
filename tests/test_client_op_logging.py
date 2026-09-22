"""各 frame 客户端按调用顺序写入 request_log。全程 mock，不连真实中间件。"""
import inspect
from unittest.mock import MagicMock

import pytest

from frame import request_log
from frame.db_client import DBClient
from frame.http_client import HttpClient
from frame.mq_client import MqClient
from frame.redis_client import RedisClient


@pytest.fixture(autouse=True)
def _reset_log():
    request_log.reset()
    yield
    request_log.reset()


def _dump_text(tmp_path, name="test_case"):
    path = request_log.dump(name, str(tmp_path))
    assert path is not None
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _fake_db_conn(fetchall=None, fetchone=None, rowcount=1):
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False
    cursor.fetchall.return_value = fetchall if fetchall is not None else [{"id": 1}]
    cursor.fetchone.return_value = fetchone
    cursor.execute.return_value = rowcount
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def test_db_query_logs_params_and_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "frame.db_client.get_db_config",
        lambda name: {"host": "h", "port": 3306, "user": "u", "password": "p", "database": "d"},
    )
    conn = _fake_db_conn(fetchall=[{"id": 9}])
    monkeypatch.setattr("frame.db_client.pymysql.connect", lambda **kwargs: conn)

    client = DBClient("order_db")
    rows = client.query("SELECT * FROM orders WHERE id=%s", (9,))

    assert rows == [{"id": 9}]
    content = _dump_text(tmp_path)
    assert "## 1 · DB query" in content
    assert "SELECT * FROM orders WHERE id=%s" in content
    assert "order_db" in content
    assert '"id": 9' in content


def test_db_execute_failure_is_still_logged(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "frame.db_client.get_db_config",
        lambda name: {"host": "h", "port": 3306, "user": "u", "password": "p", "database": "d"},
    )
    conn = _fake_db_conn()
    conn.cursor.return_value.execute.side_effect = RuntimeError("deadlock")
    monkeypatch.setattr("frame.db_client.pymysql.connect", lambda **kwargs: conn)

    client = DBClient("order_db")
    with pytest.raises(RuntimeError, match="deadlock"):
        client.execute("UPDATE orders SET status=%s", ("PAID",))

    content = _dump_text(tmp_path)
    assert "## 1 · DB execute" in content
    assert "UPDATE orders SET status=%s" in content
    assert "deadlock" in content


def test_redis_get_and_set_keep_order(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "frame.redis_client.get_redis_config",
        lambda name: {"host": "127.0.0.1", "port": 6379, "password": "", "db": 0},
    )
    fake = MagicMock()
    fake.get.return_value = None
    fake.set.return_value = True
    monkeypatch.setattr("frame.redis_client.redis.Redis", lambda **kwargs: fake)

    client = RedisClient("main_cache")
    client.set("foo", {"a": 1}, ex=300)
    client.get("foo")

    content = _dump_text(tmp_path)
    set_at = content.index("## 1 · REDIS set")
    get_at = content.index("## 2 · REDIS get")
    assert set_at < get_at
    assert '"key": "foo"' in content
    assert "300" in content


def test_all_redis_methods_are_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "frame.redis_client.get_redis_config",
        lambda name: {"host": "127.0.0.1", "port": 6379, "password": "", "db": 0},
    )
    fake = MagicMock()
    monkeypatch.setattr("frame.redis_client.redis.Redis", lambda **kwargs: fake)

    client = RedisClient("main_cache")
    client.zadd("k", {"m": 1.0}, ex=10)
    client.zrange("k")
    client.zrangebyscore("k")
    client.hset("k", "f", 1, ex=5)
    client.hmset("k", {"f": 1})
    client.hget("k", "f")
    client.hgetall("k")
    client.expire("k", 10)
    client.delete("k")

    content = _dump_text(tmp_path)
    names = [
        "zadd",
        "zrange",
        "zrangebyscore",
        "hset",
        "hmset",
        "hget",
        "hgetall",
        "expire",
        "delete",
    ]
    positions = [content.index("## %d · REDIS %s" % (i, name)) for i, name in enumerate(names, start=1)]
    assert positions == sorted(positions)
    assert "- 操作次数：9" in content


def test_mq_send_logs_then_raises(tmp_path):
    with pytest.raises(NotImplementedError):
        MqClient.send(topic="order.paid", data={"orderId": "1001"})

    content = _dump_text(tmp_path)
    assert "## 1 · MQ send" in content
    assert "order.paid" in content
    assert "1001" in content
    assert "未实现" in content


def test_mq_pull_logs_then_raises(tmp_path):
    with pytest.raises(NotImplementedError):
        MqClient.pull(subject="order.paid", group="g", timeout=1000, batch=10)

    content = _dump_text(tmp_path)
    assert "## 1 · MQ pull" in content
    assert "order.paid" in content


def _public_callables(cls):
    items = []
    for name, value in vars(cls).items():
        if name.startswith("_"):
            continue
        if isinstance(value, classmethod):
            items.append((name, value.__func__))
        elif inspect.isfunction(value):
            items.append((name, value))
    return items


def test_db_redis_mq_public_methods_all_logged():
    """新增公开方法时必须挂 logged，避免漏记。"""
    missing = []
    for cls in (DBClient, RedisClient, MqClient):
        for name, fn in _public_callables(cls):
            if not getattr(fn, "__wrapped__", None):
                missing.append("%s.%s" % (cls.__name__, name))
    assert missing == []


def test_mixed_clients_follow_call_order(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "frame.db_client.get_db_config",
        lambda name: {"host": "h", "port": 3306, "user": "u", "password": "p", "database": "d"},
    )
    monkeypatch.setattr(
        "frame.redis_client.get_redis_config",
        lambda name: {"host": "127.0.0.1", "port": 6379, "password": "", "db": 0},
    )
    conn = _fake_db_conn(fetchone={"id": 1})
    monkeypatch.setattr("frame.db_client.pymysql.connect", lambda **kwargs: conn)
    fake_redis = MagicMock()
    fake_redis.get.return_value = "cached"
    monkeypatch.setattr("frame.redis_client.redis.Redis", lambda **kwargs: fake_redis)

    db = DBClient("order_db")
    redis = RedisClient("main_cache")
    db.query_one("SELECT 1")
    redis.get("k")

    content = _dump_text(tmp_path)
    assert content.index("## 1 · DB query_one") < content.index("## 2 · REDIS get")
