r"""E2 三态验收用的「非 firstep 占位服务」：监听 127.0.0.1:8000。

用途：`start-app.bat` 判定「端口被谁占着」的判据是 `/api/health` 能否取回 JSON。
本占位服务返回非 JSON（纯文本目录列表），因此 start-app.bat 应走 `:port_busy`
分支弹中文弹窗并 `exit /b 1`——这就是「端口被占」态的可复现前置。

用法（后台起，验收完 kill）：
    python .scratch/newcomer-onboarding/port-holder-16.py
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler 接口
        body = b"not-firstep: this port is held by a plain file server\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # noqa: A003 - 静音
        return


if __name__ == "__main__":
    print("port holder listening on 127.0.0.1:8000", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
