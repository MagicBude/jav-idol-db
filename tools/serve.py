# -*- coding: utf-8 -*-
"""
serve.py —— 本地交互式查询服务（零外部依赖，仅用标准库 http.server）
========================================================================
把通用查询工具变成一个浏览器里能直接用的界面：

  python tools/serve.py            # 默认 http://127.0.0.1:8765
  python tools/serve.py --port 9000
  JAV_PORT=9000 python tools/serve.py

提供：
  GET /                     交互界面（tools/webui/index.html）
  GET /app.js /style.css    静态资源
  GET /api/code?code=STARS-145&source=all      多源查单部作品
  GET /api/actress?name=白桃はな                  女优页（codeav，含全量作品）
  GET /api/search?q=桃乃木かな&source=codeav      搜索（作品+女优）
  GET /api/sources                                数据源清单与说明

复用 tools/jav.py 的 fetch_product / codeav_actress / codeav_search。
沙箱只到 codeav；javbus/javdb/fanza 在本机宽网络 + Playwright 下才可用，
不可用时 API 返回 ok:false 而非崩溃（前端优雅提示）。
"""
import os
import sys
import json
import argparse
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from jav import (  # noqa: E402
    fetch_product, codeav_actress, codeav_search, SOURCES, SOURCE_DESC,
)

WEBUI = os.path.join(HERE, "webui")
PORT = int(os.environ.get("JAV_PORT", "8765"))

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


# --------------------------------------------------------------------------
# API 处理
# --------------------------------------------------------------------------
def api_code(code, source):
    sources = [s.strip() for s in source.split(",") if s.strip()] if source else ["codeav"]
    if not sources:
        sources = ["codeav"]
    merged, results = fetch_product(code, sources)
    if not merged:
        return {"ok": False, "error": "未命中", "sources": results}, 404
    return {"ok": True, **merged, "sources": results}, 200


def api_actress(name):
    r = codeav_actress(name)
    if not r:
        return {"ok": False, "error": "未找到女优"}, 404
    return {"ok": True, **r}, 200


def api_search(q, source):
    # 搜索目前由 codeav 提供结构化结果（作品+女优）。
    # 若指定了其它源，则退化为「把 q 当番号查」的多源作品查询。
    if source and source != "codeav":
        merged, results = fetch_product(q, [s.strip() for s in source.split(",") if s.strip()] or ["codeav"])
        if merged:
            return {"ok": True, "kind": "code", **merged, "sources": results}, 200
        return {"ok": False, "error": "未命中"}, 404
    r = codeav_search(q)
    return {"ok": True, **r}, 200


def api_sources():
    return {"ok": True, "sources": {n: SOURCE_DESC.get(n, "") for n in SOURCES}}, 200


# --------------------------------------------------------------------------
# HTTP Handler
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 静默默认访问日志
        pass

    def _send_json(self, obj, status):
        body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        ct = _CONTENT_TYPES.get(ext, "application/octet-stream")
        try:
            with open(path, "rb") as f:
                body = f.read()
        except Exception:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        q = urllib.parse.parse_qs(parsed.query)

        # ---- API ----
        if path == "/api/code":
            code = (q.get("code") or [""])[0]
            if not code:
                return self._send_json({"ok": False, "error": "缺少 code"}, 400)
            return self._send_json(*api_code(code, (q.get("source") or ["codeav"])[0]))
        if path == "/api/actress":
            name = (q.get("name") or [""])[0]
            if not name:
                return self._send_json({"ok": False, "error": "缺少 name"}, 400)
            return self._send_json(*api_actress(name))
        if path == "/api/search":
            qq = (q.get("q") or [""])[0]
            if not qq:
                return self._send_json({"ok": False, "error": "缺少 q"}, 400)
            return self._send_json(*api_search(qq, (q.get("source") or ["codeav"])[0]))
        if path == "/api/sources":
            return self._send_json(*api_sources())

        # ---- 静态前端 ----
        if path in ("/", "/index.html"):
            return self._send_file(os.path.join(WEBUI, "index.html"))
        if path in ("/app.js", "/style.css"):
            return self._send_file(os.path.join(WEBUI, path.lstrip("/")))
        # 其它静态（如 favicon）
        fp = os.path.normpath(os.path.join(WEBUI, path.lstrip("/")))
        if fp.startswith(WEBUI) and os.path.isfile(fp):
            return self._send_file(fp)
        self.send_response(404)
        self.end_headers()


def main():
    ap = argparse.ArgumentParser(description="JAV 查询台 —— 本地交互服务")
    ap.add_argument("--port", type=int, default=PORT, help="监听端口")
    ap.add_argument("--host", default="127.0.0.1", help="监听地址")
    args = ap.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"JAV 查询台已启动：{url}")
    print(f"数据源：{', '.join(SOURCES.keys())}（沙箱仅 codeav 可达，其余需本机宽网络+Playwright）")
    print("按 Ctrl+C 停止。")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        httpd.shutdown()


if __name__ == "__main__":
    main()
