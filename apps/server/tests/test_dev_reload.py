from run import uvicorn_dev_kwargs


def test_dev_reload_watches_app_not_runtime_data():
    """Python 扩展会往 data/code-server 写 pythonrc.py；热重载不能盯这块。"""
    kw = uvicorn_dev_kwargs()
    assert kw["reload"] is True
    assert kw["reload_dirs"] == ["app"]
