"""
示例测试用例
演示 HTTP / DB / Redis 客户端的用法。
DB、Redis 依赖真实环境，默认 skip；复制到业务仓库后去掉 skip 并换成真实配置。
"""
import pytest

from frame.jsonpath_utils import assert_jp, jp


class TestHttpExample:
    """HTTP 接口请求示例（响应统一走 jsonpath 断言）"""

    def test_get_request(self, http_client):
        """示例：发送 GET 请求，断言 jsonpath 字段"""
        client = http_client(base_url="https://httpbin.org")
        resp = client.get("/get", params={"key": "value"})

        assert resp.status_code == 200
        assert_jp(resp.json(), "$.args.key", "value")

    def test_post_request(self, http_client):
        """示例：发送 POST 请求（JSON body），断言 jsonpath 字段"""
        client = http_client(base_url="https://httpbin.org")
        payload = {"name": "test", "age": 18}
        resp = client.post("/post", json=payload)

        assert resp.status_code == 200
        body = resp.json()
        assert_jp(body, "$.json.name", "test")
        assert_jp(body, "$.json.age", 18)

    def test_post_with_full_url(self, http_client):
        """示例：使用完整 URL 发送请求（不依赖 base_url）"""
        client = http_client()
        resp = client.get("https://httpbin.org/get")

        assert resp.status_code == 200
        # 存在性断言：无匹配即失败，失败信息里带 path
        jp(resp.json(), "$.url")


@pytest.mark.skip(reason="需要真实 MySQL，并把 config.yaml 里的连接信息改成可用值")
class TestDBExample:
    """数据库操作示例"""

    def test_query(self, db_client):
        """示例：查询数据"""
        db = db_client("main_db")
        results = db.query("SELECT 1 AS num")

        assert results[0]["num"] == 1

    def test_query_one(self, db_client):
        """示例：查询单条数据"""
        db = db_client("main_db")
        result = db.query_one("SELECT 1 AS num")

        assert result["num"] == 1

    def test_execute_with_params(self, db_client):
        """示例：带参数执行 SQL（防 SQL 注入）"""
        db = db_client("main_db")
        results = db.query("SELECT %s AS name", ("test_user",))

        assert results[0]["name"] == "test_user"

    def test_multiple_db(self, db_client):
        """示例：同时操作多个数据库"""
        main_db = db_client("main_db")
        order_db = db_client("order_db")

        result1 = main_db.query_one("SELECT DATABASE() AS db_name")
        result2 = order_db.query_one("SELECT DATABASE() AS db_name")

        assert result1["db_name"] != result2["db_name"]


@pytest.mark.skip(reason="需要真实 Redis 连接，请先在 config.yaml 的 redis 段填连接信息")
class TestRedisExample:
    """Redis 操作示例。redis_client 的参数是集群名，例如 IBU_xxx_cache。"""

    def test_set_and_get(self, redis_client):
        """示例：设置和获取值"""
        cache = redis_client("main_cache")

        cache.set("test_key", "test_value", ex=60)
        value = cache.get("test_key")

        assert value == "test_value"

        cache.delete("test_key")

    def test_hash_operations(self, redis_client):
        """示例：哈希表操作"""
        cache = redis_client("main_cache")

        cache.hset("test_hash", "field1", "value1")
        cache.hmset("test_hash", {"field2": "value2", "field3": "value3"})

        value = cache.hget("test_hash", "field1")
        assert value == "value1"

        all_data = cache.hgetall("test_hash")
        assert all_data["field2"] == "value2"

        cache.delete("test_hash")


class TestIntegrationExample:
    """综合示例：接口请求 + DB 验证 + Redis 缓存"""

    def test_api_with_db_verification(self, http_client, db_client):
        """
        示例：调用接口后，通过数据库验证数据是否正确写入
        （以下为伪代码示例，实际使用时替换为真实接口和表）
        """
        client = http_client(base_url="https://httpbin.org")
        resp = client.post("/post", json={"order_id": "12345"})
        assert resp.status_code == 200

        # db = db_client("order_db")
        # result = db.query_one("SELECT * FROM orders WHERE order_id = %s", ("12345",))
        # assert result is not None
        # assert result["status"] == "created"

    def test_api_with_cache_check(self, http_client, redis_client):
        """
        示例：调用接口后，验证 Redis 缓存是否更新
        （以下为伪代码示例，实际使用时替换为真实逻辑）
        """
        client = http_client(base_url="https://httpbin.org")
        resp = client.get("/get", params={"user_id": "100"})
        assert resp.status_code == 200

        # cache = redis_client("main_cache")
        # cached_value = cache.get("user:100:profile")
        # assert cached_value is not None
