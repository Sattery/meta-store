"""logger.py — 简易日志模块。

级别: 默认 INFO，环境变量 META_STORE_LOG=DEBUG 可开启详细日志。
输出: 终端 stderr（不干扰 HTTP 响应流）。
"""

import os
import sys
import time

_level = os.environ.get("META_STORE_LOG", "INFO").upper()
_LEVELS = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}
_CURRENT = _LEVELS.get(_level, 1)


def _log(level: str, msg: str):
    if _LEVELS.get(level, 99) >= _CURRENT:
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] [{level:5s}] {msg}", file=sys.stderr, flush=True)


def debug(msg: str):
    _log("DEBUG", msg)


def info(msg: str):
    _log("INFO", msg)


def warn(msg: str):
    _log("WARN", msg)


def error(msg: str):
    _log("ERROR", msg)
