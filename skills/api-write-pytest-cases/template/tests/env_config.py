"""
环境常量。Pod IP、环境、appid 变更时只改这一个文件。

业务断言常量（错误码、模板 ID、期望值）不要放这里，放到各自的用例文件里，
避免所有文件都依赖同一个大常量池。
"""
APP_ID = "100023456"
ENV_NAME = "fat8"
POD_IP = "10.x.x.x"
OPERATION = "api/xxx"
