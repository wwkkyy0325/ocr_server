# -*- coding: utf-8 -*-
# 文件说明：
# - 作用：自动化校验的简易 HTTP 服务端，提供健康检查与执行接口
# - 核心实现：基于 http.server 实现 /automation/run，同步调用 AutomationVerificationService
# - 关联关系：与 automation.task_manager 配合对外提供自动化能力
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from app.automation.task_manager import AutomationVerificationService


automation_service = AutomationVerificationService()


class AutomationHttpHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path == "/automation/run":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except Exception:
                self._send_json(400, {"error": "invalid_json"})
                return
            id_cards = payload.get("id_cards") or []
            config = payload.get("config") or {}
            if not isinstance(id_cards, list):
                self._send_json(400, {"error": "id_cards_must_be_list"})
                return
            try:
                results = automation_service.run_sync(id_cards, config)
                self._send_json(200, {"results": results})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
        else:
            self._send_json(404, {"error": "not_found"})


def run_server(host="127.0.0.1", port=8081):
    server = HTTPServer((host, port), AutomationHttpHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
