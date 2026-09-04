"""
基于 redis-py 的 Redis 集群客户端，封装 string / zset / hash 常用操作。

每个实例对应一个 Redis 集群（或单机），通过 cluster_name 从 config.yaml 的
`redis` 段读连接信息。

`read_master` 保留为**接口参数**：核心通用实现是单节点 redis-py，主从分离在此层
不生效，参数只是原样存下；vendor 适配（支持主从读写分离的 Redis 客户端）覆盖本文件时
才会真正使用它决定读走 master 还是 slave。默认 False 与适配层"读默认走 slave"的
语义一致。

用法：
    client = RedisClient("main_cache")
    client.set("foo", {"a": 1}, ex=300)
    val = client.get("foo")
    client.delete("foo")
"""

import json
from typing import Any, Dict, List, Optional, Tuple, Union

import redis

from .config import get_redis_config


def _dump(value: Any) -> Any:
    if isinstance(value, (str, bytes)):
        return value
    return json.dumps(value, ensure_ascii=False)


class RedisClient:
    """通用 Redis 客户端。"""

    def __init__(self, cluster_name: str, read_master: bool = False) -> None:
        cfg = get_redis_config(cluster_name)
        self._client = redis.Redis(
            host=cfg["host"],
            port=cfg.get("port", 6379),
            password=cfg.get("password"),
            db=cfg.get("db", 0),
            decode_responses=True,
        )
        # 核心通用实现里 read_master 不生效；参数保留供 vendor 适配层使用
        self._read_master = read_master

    def get(self, key: str) -> Optional[str]:
        return self._client.get(key)

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        return bool(self._client.set(key, _dump(value), ex=ex))

    def zadd(
        self,
        key: str,
        mapping: Dict[str, float],
        ex: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> int:
        result = self._client.zadd(key, mapping, nx=nx, xx=xx)
        if ex is not None:
            self._client.expire(key, ex)
        return result

    def zrange(
        self,
        key: str,
        start: int = 0,
        end: int = -1,
        desc: bool = False,
        withscores: bool = False,
    ) -> List[Union[str, Tuple[str, float]]]:
        return self._client.zrange(key, start, end, desc=desc, withscores=withscores)

    def zrangebyscore(
        self,
        key: str,
        min_score: Union[float, str] = "-inf",
        max_score: Union[float, str] = "+inf",
        withscores: bool = False,
        offset: Optional[int] = None,
        count: Optional[int] = None,
    ) -> List[Union[str, Tuple[str, float]]]:
        return self._client.zrangebyscore(
            key,
            min_score,
            max_score,
            start=offset,
            num=count,
            withscores=withscores,
        )

    def hset(self, key: str, field: str, value: Any, ex: Optional[int] = None) -> int:
        result = self._client.hset(key, field, _dump(value))
        if ex is not None:
            self._client.expire(key, ex)
        return result

    def hmset(self, key: str, mapping: Dict[str, Any], ex: Optional[int] = None) -> bool:
        """
        批量设置 Hash 字段。非 str/bytes 会 JSON 序列化。

        底层已改用 `hset(key, mapping=...)`（redis-py 4.x 起 `hmset` 已废弃）；
        方法名保留 `hmset` 是为让老用例代码不用改。
        """
        serialized = {f: _dump(v) for f, v in mapping.items()}
        result = self._client.hset(key, mapping=serialized)
        if ex is not None:
            self._client.expire(key, ex)
        return bool(result)

    def hget(self, key: str, field: str) -> Optional[str]:
        return self._client.hget(key, field)

    def hgetall(self, key: str) -> Dict[str, str]:
        return self._client.hgetall(key) or {}

    def expire(self, key: str, seconds: int) -> bool:
        return bool(self._client.expire(key, seconds))

    def delete(self, key: str) -> int:
        return self._client.delete(key)
