"""
消息中间件（MQ）客户端占位。

本文件是核心模板的通用占位，默认 raise NotImplementedError。
使用具体 MQ（Kafka / RocketMQ / RabbitMQ / 自研网关等）时，将本文件替换成
真正的实现，保持 send / pull 两个类方法签名不变，用例代码即可无感切换。

签名约定：

    MqClient.send(topic: str, data: dict, **kwargs) -> dict
        发送一条消息到指定 topic，kwargs 由具体实现自行使用（如顺序 key、子环境）。

    MqClient.pull(subject: str, group: str, timeout: int, batch: int, **kwargs) -> list[dict]
        从指定 subject + group 拉取消息，用于验证接口副作用。
        timeout 单位毫秒，batch 单次最大条数。
"""


class MqClient:
    """MQ 客户端占位。核心模板不提供实现，由适配层替换。"""

    @classmethod
    def send(cls, topic: str, data: dict, **kwargs) -> dict:
        raise NotImplementedError(
            "MqClient.send 未实现。请安装对应的 vendor 适配 skill，"
            "或按项目实际使用的 MQ 类型自行替换 frame/mq_client.py。"
        )

    @classmethod
    def pull(cls, subject: str, group: str, timeout: int, batch: int, **kwargs) -> list:
        raise NotImplementedError(
            "MqClient.pull 未实现。请安装对应的 vendor 适配 skill，"
            "或按项目实际使用的 MQ 类型自行替换 frame/mq_client.py。"
        )
