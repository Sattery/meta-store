#!/usr/bin/env python3
"""server.py — Meta Store 本地服务端。

提供 HTTP API 供 editor.html 调用，实现：
  - 输入路径 → 扫描目录树 → 存入集中存储
  - 编辑 des → 保存
  - 管理多个路径的元数据

存储路径: 见 config.json（默认 .metastore/meta-store.json）
启动: python -m meta_store.server [--port 8765]
"""

import json
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

from meta_store.scanner import merge_des_from_tree, scan_path, sync_des_across_entries
from meta_store.store import load_store, save_store, STORE_FILE, DATA_DIR
from meta_store.config import load_config, save_config, CONFIG_FILE

# ── 配置 ──────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent
EDITOR_FILE = ROOT_DIR / "static" / "editor.html"

DEFAULT_PORT = 8765
DEFAULT_DEPTH = 2
DEFAULT_FIELDS = "size,modified,file_count,total_size_human"
DEFAULT_EXCLUDE = "meta.json,.workbuddy,node_modules,.git"

# ── 存储读写锁 ────────────────────────────────────────────────

_store_lock = threading.Lock()


# ── HTTP Handler ──────────────────────────────────────────────

class MetaHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # 简化日志
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, fp: Path, content_type: str):
        if not fp.exists():
            self.send_error(404, "Not Found")
            return
        body = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def do_OPTIONS(self):
        self._send_json({"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._send_file(EDITOR_FILE, "text/html; charset=utf-8")
            return

        if path == "/api/store":
            with _store_lock:
                store = load_store()
            self._send_json(store)
            return

        if path == "/api/paths":
            with _store_lock:
                store = load_store()
            paths = list(store.get("paths", {}).keys())
            self._send_json({"paths": paths})
            return

        if path == "/api/config":
            cfg = load_config()
            cfg["_config_file"] = str(CONFIG_FILE)
            self._send_json(cfg)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/scan":
            self._handle_scan()
            return

        if path == "/api/save":
            self._handle_save()
            return

        if path == "/api/remove":
            self._handle_remove()
            return

        if path == "/api/config":
            self._handle_config()
            return

        self.send_error(404, "Not Found")

    # ── API: 扫描路径 ──
    def _handle_scan(self):
        body = self._read_body()
        raw_path = body.get("path", "").strip()
        if not raw_path:
            self._send_json({"error": "缺少 path 参数"}, 400)
            return

        target = Path(raw_path).resolve()
        if not target.is_dir():
            self._send_json({"error": f"'{target}' 不是有效目录"}, 400)
            return

        depth = body.get("depth", DEFAULT_DEPTH)
        fields = body.get("fields", DEFAULT_FIELDS)
        exclude = body.get("exclude", DEFAULT_EXCLUDE)
        dirs_only = body.get("dirs_only", False)

        try:
            new_tree = scan_path(
                target,
                depth=depth,
                fields_str=fields,
                exclude_names=exclude,
                dirs_only=dirs_only,
            )
        except Exception as e:
            self._send_json({"error": f"扫描失败: {e}"}, 500)
            return

        # 合并已存 des
        with _store_lock:
            store = load_store()
            key = str(target)
            old_tree = store["paths"].get(key, {}).get("tree")
            new_tree = merge_des_from_tree(new_tree, old_tree)

            # 从其他 entry 收集 des 合并到新树（解决先扫子目录后扫父目录的同步）
            all_des = {}
            sep = "\\" if "\\" in key else "/"
            for pkey, entry in store["paths"].items():
                if pkey == key or not entry.get("tree"):
                    continue
                root_d = entry["tree"].get("des", "").strip()
                if root_d:
                    all_des[pkey] = root_d
                from meta_store.scanner import flatten_des, merge_des
                tree_des = flatten_des(entry["tree"].get("items", []), pkey)
                all_des.update(tree_des)
            if all_des:
                merge_des(new_tree.get("items", []), all_des)

            # 存入
            store["paths"][key] = {
                "path": key,
                "name": target.name,
                "des": new_tree.get("des", ""),
                "scanned_at": new_tree.get("scan_time", ""),
                "scan_config": {
                    "depth": depth,
                    "fields": fields,
                    "exclude": exclude,
                    "dirs_only": dirs_only,
                },
                "tree": new_tree,
            }
            save_store(store)

        self._send_json({
            "ok": True,
            "path": key,
            "tree": new_tree,
        })

    # ── API: 保存 des ──
    def _handle_save(self):
        body = self._read_body()
        path_key = body.get("path", "").strip()
        tree = body.get("tree")

        if not path_key or tree is None:
            self._send_json({"error": "缺少 path 或 tree 参数"}, 400)
            return

        with _store_lock:
            store = load_store()
            if path_key not in store["paths"]:
                self._send_json({"error": "路径不存在，请先扫描"}, 400)
                return

            entry = store["paths"][path_key]
            # 保留 scan_config，更新 tree 和 des
            entry["tree"] = tree
            entry["des"] = tree.get("des", "")
            # 跨 entry 同步 des（子目录/父目录共享同一描述）
            sync_des_across_entries(store, path_key)
            save_store(store)

        self._send_json({"ok": True})

    # ── API: 移除路径 ──
    def _handle_remove(self):
        body = self._read_body()
        path_key = body.get("path", "").strip()

        with _store_lock:
            store = load_store()
            if path_key in store["paths"]:
                del store["paths"][path_key]
                save_store(store)
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "路径不存在"}, 404)

    # ── API: 配置读写 ──
    def _handle_config(self):
        body = self._read_body()
        # 合并写入：只更新传过来的字段
        cfg = load_config()
        for k in ("store_path", "port", "auto_open_browser"):
            if k in body:
                cfg[k] = body[k]
        save_config(cfg)
        cfg["_config_file"] = str(CONFIG_FILE)
        self._send_json({"ok": True, "config": cfg})


# ── 启动 ──────────────────────────────────────────────────────

def find_free_port(preferred: int) -> int:
    """优先用 preferred，被占用则递增。"""
    import socket
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred


def main():
    import argparse
    cfg = load_config()
    p = argparse.ArgumentParser(description="Meta Store 本地服务端")
    p.add_argument("--port", type=int, default=None,
                   help=f"端口（默认从 config 读取: {cfg.get('port', DEFAULT_PORT)}）")
    p.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = p.parse_args()

    port = args.port or cfg.get("port", DEFAULT_PORT)

    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "buffer"):
                stream.reconfigure(encoding="utf-8")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    port = find_free_port(port)
    server = HTTPServer(("127.0.0.1", port), MetaHandler)

    url = f"http://127.0.0.1:{port}"
    print(f"Meta Store 服务已启动: {url}")
    print(f"存储文件: {STORE_FILE}")
    print("按 Ctrl+C 停止")
    print()

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
