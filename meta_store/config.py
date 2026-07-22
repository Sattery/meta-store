"""config.py — Meta Store 配置管理。

路径逻辑：
  - 打包环境 (exe):  同目录 .metastore/ (隐藏目录)
  - 源码环境:        项目根 data/

配置项:
  store_path        存储文件路径（相对 base_dir 或绝对路径）
  port              HTTP 服务端口（默认 8765）
  auto_open_browser 启动时是否自动打开浏览器
  exclude_patterns  扫描时排除的文件/目录名正则列表
"""

import json
import os
import re
import sys
from pathlib import Path
from copy import deepcopy


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _get_data_dir_name() -> str:
    """exe 用隐藏目录 .metastore，源码用 data。"""
    return ".metastore" if _is_frozen() else "data"


# ── 默认配置 ──────────────────────────────────────────────────

DEFAULTS = {
    "store_path": _get_data_dir_name() + "/meta-store.json",
    "port": 8765,
    "auto_open_browser": True,
    "exclude_patterns": [
        r"^\..*",       # 隐藏文件/文件夹
        "node_modules",
        "__pycache__",
        "dist",
        "build",
    ],
}


def _get_base_dir() -> Path:
    """确定基准目录（config.json 和数据文件的父级）。"""
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# ── 路径 ──────────────────────────────────────────────────────

BASE_DIR = _get_base_dir()
DATA_DIR = BASE_DIR / _get_data_dir_name()
CONFIG_FILE = DATA_DIR / "config.json"


# ── 读写 ──────────────────────────────────────────────────────

def load_config() -> dict:
    """加载配置。文件不存在时返回默认配置。"""
    cfg = deepcopy(DEFAULTS)
    if not CONFIG_FILE.exists():
        return cfg
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            cfg.update(raw)
    except (json.JSONDecodeError, OSError):
        pass
    return cfg


def save_config(config: dict):
    """保存配置。只保留与默认值不同的键。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 只保存与默认不同的值（保持配置整洁）
    cleaned = {}
    for k, v in config.items():
        if k in DEFAULTS and v != DEFAULTS[k]:
            cleaned[k] = v

    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(str(tmp), str(CONFIG_FILE))


def get_store_path() -> Path:
    """解析 store_path 配置。

    相对路径 → 相对于 BASE_DIR 解析；绝对路径 → 直接使用。
    """
    cfg = load_config()
    raw = cfg.get("store_path", DEFAULTS["store_path"])
    p = Path(raw)
    if not p.is_absolute():
        p = (BASE_DIR / p).resolve()
    return p
