#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""serve.py — 本地静态服务器

汉维踩过的坑：Python http.server 在某些 Windows 版本上把 .svg / .woff2
标成非标准 MIME，浏览器直接拒绝解码，页面看起来「图标坏了」。
这里显式指定 MIME。

    python tools/serve.py            # 默认 5200
    python tools/serve.py 5300
"""
import http.server
import os
import socketserver
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".svg": "image/svg+xml",
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".ttf": "font/ttf",
        ".ico": "image/x-icon",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".html": "text/html; charset=utf-8",
    }

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=APP, **kw)

    def end_headers(self):
        # 本地开发禁用缓存，改完刷新即生效
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        # 只报错误，避免刷屏
        if args and str(args[1])[:1] in ("4", "5"):
            sys.stderr.write("%s %s\n" % (args[0], args[1]))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5200
    os.chdir(APP)
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler) as httpd:
        kind = "http://localhost:%d/v1" % port
        print("漢法辭典 本地預覽： http://localhost:%d/" % port)
        print("繁體： http://localhost:%d/?q=學生" % port)
        print("法語： http://localhost:%d/?q=livre" % port)
        print("（Ctrl+C 停止）")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n停止。")


if __name__ == "__main__":
    main()