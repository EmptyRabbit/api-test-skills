"""HttpClient 自动记录请求日志的验证测试。用标准库起本地服务，不依赖外网。"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from frame import request_log
from frame.http_client import HttpClient


class _EchoHandler(BaseHTTPRequestHandler):
    """收到什么都回固定 JSON，够验证日志链路。"""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = json.dumps({"success": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def test_post_is_recorded_without_touching_the_case(tmp_path):
    """用例侧不写任何日志代码，请求与响应也要被记下来。"""
    server = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    request_log.reset()
    client = HttpClient(base_url="http://127.0.0.1:%d" % server.server_port)
    resp = client.post("echo", json={"cid": "37002090310729793169"})
    client.close()
    server.shutdown()

    assert resp.status_code == 200

    path = request_log.dump("test_post_is_recorded", str(tmp_path))
    assert path is not None
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    assert "POST /echo" in content
    assert "37002090310729793169" in content
    assert '"success": true' in content
