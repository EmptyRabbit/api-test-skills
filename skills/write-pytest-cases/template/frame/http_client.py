import httpx

from . import request_log


class HttpClient:
    """HTTP 请求客户端，基于 httpx 库封装"""

    def __init__(self, base_url=None, headers=None, timeout=30):
        """
        Args:
            base_url: 基础 URL，后续请求可只传路径
            headers: 默认请求头
            timeout: 默认超时时间（秒）
        """
        self.base_url = base_url.rstrip('/') if base_url else ''
        self.timeout = timeout
        self.client = httpx.Client(headers=headers or {})

    def _build_url(self, path):
        if path.startswith(('http://', 'https://')):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def get(self, path, params=None, headers=None, **kwargs):
        """发送 GET 请求。请求与响应会自动记入用例日志。"""
        url = self._build_url(path)
        resp = self.client.get(url, params=params, headers=headers or {}, timeout=self.timeout, **kwargs)
        # 日志记录失败不能影响真实请求的返回
        try:
            request_log.add(resp)
        except Exception:
            pass
        return resp

    def post(self, path, json=None, data=None, headers=None, **kwargs):
        """发送 POST 请求。请求与响应会自动记入用例日志。"""
        url = self._build_url(path)
        resp = self.client.post(url, json=json, data=data, headers=headers or {}, timeout=self.timeout, **kwargs)
        # 日志记录失败不能影响真实请求的返回
        try:
            request_log.add(resp)
        except Exception:
            pass
        return resp

    def close(self):
        self.client.close()
