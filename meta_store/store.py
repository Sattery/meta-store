"""store.py — Meta Store 读写与备份。

集中管理 meta-store.json 的加载、保存、查询。
供 server.py（HTTP 服务端）和 meta-store.py（CLI）共用。

存储路径由 config.json 的 store_path 控制：
  - 相对路径 → 相对于基准目录（exe 或项目根目录）
  - 绝对路径 → 直接使用
  - 默认: .metastore/meta-store.json
"""

import json
import os
from datetime import datetime
from pathlib import Path

from meta_store.config import get_store_path

# ── 路径 ──────────────────────────────────────────────────────

def _resolve_paths():
    """解析存储文件路径，返回 (store_file, data_dir, backup_file)。"""
    store = get_store_path()
    data_dir = store.parent
    backup = data_dir / (store.stem + ".bak")
    return store, data_dir, backup

STORE_FILE, DATA_DIR, BACKUP_FILE = _resolve_paths()


# ── 读 ────────────────────────────────────────────────────────

def load_store() -> dict:
    """加载存储文件。不存在时返回空结构。"""
    if not STORE_FILE.exists():
        return {"version": 1, "updated_at": "", "paths": {}}
    try:
        data = json.loads(STORE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "paths" in data:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"version": 1, "updated_at": "", "paths": {}}


# ── 写（含备份）─────────────────────────────────────────────────

def save_store(store: dict):
    """原子写入存储文件。

    备份策略（1 份）：
      - 若 meta-store.json 存在 → 先原地改名为 meta-store.json.bak
      - 再写入新内容到 meta-store.json
      - 若写入失败 → 尝试从 .bak 恢复
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    store["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1 份备份：将当前文件改为 .bak
    if STORE_FILE.exists():
        try:
            os.replace(str(STORE_FILE), str(BACKUP_FILE))
        except OSError:
            pass  # 备份失败不阻塞保存

    # 原子写入
    tmp = STORE_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(store, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(str(tmp), str(STORE_FILE))
    except Exception:
        # 写入失败，尝试从备份恢复
        if tmp.exists():
            tmp.unlink()
        if BACKUP_FILE.exists() and not STORE_FILE.exists():
            try:
                os.replace(str(BACKUP_FILE), str(STORE_FILE))
            except OSError:
                pass
        raise


# ── 辅助 ──────────────────────────────────────────────────────

def list_paths() -> list[str]:
    """返回所有已扫描路径的列表。"""
    store = load_store()
    return sorted(store.get("paths", {}).keys())


def get_path_names() -> dict[str, str]:
    """返回 {路径: 名称} 映射。"""
    store = load_store()
    return {k: v.get("name", k) for k, v in store.get("paths", {}).items()}
