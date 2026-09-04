import os
import yaml

_config = None


def load_config(config_path=None, reload=False):
    """加载配置文件，默认读取项目根目录下的 config.yaml。

    ``config_path`` 非空时始终按该路径重读。
    ``reload=True`` 时忽略缓存，按默认路径或指定路径重新加载。
    """
    global _config
    if _config is not None and config_path is None and not reload:
        return _config

    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')

    with open(config_path, 'r', encoding='utf-8') as f:
        _config = yaml.safe_load(f)

    return _config


def get_db_config(db_name):
    """获取指定数据库的连接配置"""
    config = load_config()
    db_configs = config.get('databases', {})
    if db_name not in db_configs:
        raise KeyError(f"数据库配置 '{db_name}' 不存在，可用配置: {list(db_configs.keys())}")
    return db_configs[db_name]


def get_redis_config(cluster_name: str) -> dict:
    """
    从 config.yaml 的 redis 段读连接信息。

    config.yaml 示例：
        redis:
          main_cache:
            host: "127.0.0.1"
            port: 6379
            password: ""
            db: 0
    """
    config = load_config()
    redis_configs = config.get('redis') or {}
    if cluster_name not in redis_configs:
        raise KeyError(
            f"Redis 集群配置 {cluster_name!r} 不存在，"
            f"可用集群：{list(redis_configs.keys())}"
        )
    return redis_configs[cluster_name]
