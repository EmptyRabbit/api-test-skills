"""frame/config.py 的缓存与重载行为。全程离线，用临时 yaml，不碰真实环境。"""
import yaml
import pytest

from frame import config as cfg


@pytest.fixture(autouse=True)
def reset_config_cache():
    cfg._config = None
    yield
    cfg._config = None


def _write_yaml(path, payload):
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def test_explicit_path_always_rereads(tmp_path):
    """config_path 非空时必须按该路径重读，不能继续返回上一份缓存。"""
    first = tmp_path / "a.yaml"
    second = tmp_path / "b.yaml"
    _write_yaml(first, {"env": "a"})
    _write_yaml(second, {"env": "b"})

    assert cfg.load_config(str(first))["env"] == "a"
    assert cfg.load_config(str(second))["env"] == "b"


def test_same_path_rereads_after_file_change(tmp_path):
    """同一路径再次传入时也应重读，文件改了就能看到新值。"""
    path = tmp_path / "cfg.yaml"
    _write_yaml(path, {"env": "old"})
    assert cfg.load_config(str(path))["env"] == "old"

    _write_yaml(path, {"env": "new"})
    assert cfg.load_config(str(path))["env"] == "new"


def test_default_call_keeps_cache(tmp_path):
    """未指定 path 且 reload=False 时继续用缓存，即使磁盘上的文件已经变了。"""
    path = tmp_path / "cfg.yaml"
    _write_yaml(path, {"env": "cached"})
    cfg.load_config(str(path))

    _write_yaml(path, {"env": "changed-on-disk"})
    assert cfg.load_config()["env"] == "cached"


def test_reload_true_without_path_loads_default(tmp_path):
    """reload=True 且未指定 path 时，丢弃缓存并重读默认 config.yaml。"""
    path = tmp_path / "cfg.yaml"
    _write_yaml(path, {"env": "tmp"})
    cfg.load_config(str(path))
    assert cfg.load_config()["env"] == "tmp"

    reloaded = cfg.load_config(reload=True)
    assert "env" not in reloaded
    assert "main_db" in reloaded.get("databases", {})
