#!/usr/bin/env python3
"""tray.py — Meta Store 系统托盘常驻服务。

启动后：
  1. 后台线程运行 HTTP Server（复用 server.py 的 MetaHandler）
  2. 自动打开浏览器到编辑器页面
  3. 系统托盘显示图标，右键菜单：打开编辑器 / 退出

单实例：启动前探测端口，已被占用则只打开浏览器、不新开进程。
静默：配合 pythonw.exe 使用，无控制台黑窗口。

依赖: pystray, Pillow
"""

import os
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import HTTPServer
from pathlib import Path

# ── 路径修正：确保能 import meta_store 包 ──
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from meta_store.config import CONFIG_FILE, save_config, load_config
from meta_store.server import MetaHandler, find_free_port, DEFAULT_PORT
from meta_store.store import get_data_dir

EDITOR_URL = "http://127.0.0.1:{port}"


# ── 单实例检测 ──────────────────────────────────────────────────

def _port_in_use(port: int) -> bool:
    """探测端口是否已被占用（说明已有实例在跑）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


# ── 程序化生成托盘图标 ──────────────────────────────────────────

def _create_icon():
    """生成托盘图标：蓝色圆角方块 + 白色 M。"""
    from PIL import Image, ImageDraw, ImageFont

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 6
    radius = 14
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius,
        fill=(37, 99, 235, 255),  # #2563eb 蓝
    )

    try:
        font = ImageFont.truetype("arial.ttf", 38)
    except (OSError, IOError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "M", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    draw.text((x, y), "M", fill="white", font=font)
    return img


# ── 托盘应用 ────────────────────────────────────────────────────

class TrayApp:
    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.server: HTTPServer | None = None
        self.icon = None

    # ── 后台 HTTP Server ──

    def _start_server(self):
        get_data_dir().mkdir(parents=True, exist_ok=True)
        # 重启时重新读取 config.json，使端口等配置改动生效
        cfg = load_config()
        preferred = cfg.get("port", DEFAULT_PORT)
        self.port = find_free_port(preferred)
        self.server = HTTPServer(("127.0.0.1", self.port), MetaHandler)
        self.server.serve_forever()

    def _stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    # ── 菜单回调 ──

    def _on_open(self, icon=None, item=None):
        webbrowser.open(EDITOR_URL.format(port=self.port))

    def _on_config(self, icon=None, item=None):
        """用系统默认编辑器打开配置文件（不存在则创建默认）。"""
        if not CONFIG_FILE.exists():
            save_config(load_config())
        if sys.platform == "win32":
            os.startfile(str(CONFIG_FILE))
        else:
            subprocess.Popen(["xdg-open", str(CONFIG_FILE)])

    def _on_restart(self, icon=None, item=None):
        """停止服务 → 重新启动 → 打开浏览器。"""
        self._stop_server()
        server_thread = threading.Thread(target=self._start_server, daemon=True)
        server_thread.start()
        threading.Timer(1.0, lambda: webbrowser.open(EDITOR_URL.format(port=self.port))).start()

    def _on_exit(self, icon=None, item=None):
        self._stop_server()
        if self.icon:
            self.icon.stop()

    # ── 启动 ──

    def run(self):
        import pystray

        # 单实例检测：端口已被占用 → 只开浏览器，不启动新进程
        if _port_in_use(self.port):
            webbrowser.open(EDITOR_URL.format(port=self.port))
            # 给浏览器一点时间
            threading.Timer(0.5, sys.exit).start()
            return

        # 后台线程跑 server
        server_thread = threading.Thread(target=self._start_server, daemon=True)
        server_thread.start()

        # 等待 server 就绪后打开浏览器
        threading.Timer(1.0, lambda: webbrowser.open(EDITOR_URL.format(port=self.port))).start()

        # 托盘图标 + 右键菜单
        self.icon = pystray.Icon(
            "meta-store",
            _create_icon(),
            f"Meta Store · :{self.port}",
            menu=pystray.Menu(
                pystray.MenuItem(
                    "打开编辑器", self._on_open, default=True
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("打开配置", self._on_config),
                pystray.MenuItem("重启服务", self._on_restart),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self._on_exit),
            ),
        )
        self.icon.run()


# ── 入口 ────────────────────────────────────────────────────────

def main():
    import argparse

    p = argparse.ArgumentParser(description="Meta Store 托盘服务")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = p.parse_args()

    TrayApp(port=args.port).run()


if __name__ == "__main__":
    main()
