"""frame/mq_client.py（核心占位）的验证测试。全程离线。

核心占位的合约是：send / pull 都必须 raise NotImplementedError，
错误信息里点名让用户装 vendor 适配 skill 或自己替换。
"""
import pytest

from frame.mq_client import MqClient


def test_send_raises_not_implemented():
    """核心占位调用 send() 必须 raise NotImplementedError。"""
    with pytest.raises(NotImplementedError) as exc_info:
        MqClient.send(topic="order.paid", data={"orderId": "1001"})

    message = str(exc_info.value)
    assert "MqClient.send" in message
    assert "vendor 适配" in message


def test_pull_raises_not_implemented():
    """核心占位调用 pull() 必须 raise NotImplementedError。"""
    with pytest.raises(NotImplementedError) as exc_info:
        MqClient.pull(subject="order.paid", group="test-consumer-group", timeout=1000, batch=10)

    message = str(exc_info.value)
    assert "MqClient.pull" in message
    assert "vendor 适配" in message


def test_send_kwargs_are_ignored_but_accepted():
    """核心占位的 send 签名必须接受 **kwargs（保持与适配层一致），否则 vendor 用例代码会 TypeError。"""
    with pytest.raises(NotImplementedError):
        MqClient.send(
            topic="order.paid",
            data={"orderId": "1001"},
            app_id="example-app",
            sub_env="fat0",
            order_key="key-1",
        )


def test_pull_kwargs_are_ignored_but_accepted():
    """pull 同理必须接受 **kwargs（例如 tags）。"""
    with pytest.raises(NotImplementedError):
        MqClient.pull(
            subject="order.paid",
            group="test-consumer-group",
            timeout=1000,
            batch=10,
            tags="foo",
        )
