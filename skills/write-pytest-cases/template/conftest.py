import os

import pytest
from frame import request_log
from frame.http_client import HttpClient
from frame.db_client import DBClient
from frame.redis_client import RedisClient


@pytest.fixture
def http_client():
    """创建 HTTP 客户端。传入 base_url / headers / timeout。"""
    def _create(base_url=None, headers=None, timeout=30):
        return HttpClient(base_url=base_url, headers=headers, timeout=timeout)
    return _create


@pytest.fixture
def db_client():
    """创建 DB 客户端。传入 config.yaml 中 databases 下的库名。"""
    def _create(db_name):
        return DBClient(db_name)
    return _create


@pytest.fixture
def redis_client():
    """创建 Redis 客户端。传入 config.yaml 中 redis 下的集群名。"""
    def _create(cluster_name, read_master=False):
        return RedisClient(cluster_name, read_master=read_master)
    return _create


@pytest.fixture(autouse=True)
def log_requests(request):
    """
    自动把本用例发出的所有 HTTP 请求与响应写到 logs/<用例名>.md。

    用例代码不需要关心这个 fixture。用例失败时 teardown 照样执行，
    所以失败用例一定有日志，排障和复现直接看这个文件。
    """
    request_log.reset()
    yield
    log_dir = os.path.join(str(request.config.rootpath), "logs")
    request_log.dump(request.node.name, log_dir)
