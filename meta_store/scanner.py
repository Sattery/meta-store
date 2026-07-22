"""scanner.py — 目录树扫描核心逻辑。

从 meta-store.py 抽取，供 server.py 和 meta-store.py(CLI) 共用。
职责：构建目录树节点、统计目录信息、des 字段合并保留。

排除规则：正则列表，匹配 name 即跳过（默认 ^\\..* 排除隐藏文件）。
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

AVAILABLE_FIELDS = {
    "size":             "文件大小 (file)",
    "size_human":       "文件大小可读格式 (file)",
    "modified":         "最后修改时间",
    "created":          "创建时间",
    "file_count":       "递归文件总数 (dir)",
    "total_size":       "递归文件总大小 (dir)",
    "total_size_human": "递归文件总大小可读格式 (dir)",
}

BASE_FIELDS = {"name", "type", "des", "items"}


# ── 辅助 ──────────────────────────────────────────────────────

def format_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    for unit in ("KB", "MB", "GB", "TB"):
        nbytes /= 1024.0
        if abs(nbytes) < 1024 or unit == "TB":
            return f"{nbytes:.1f} {unit}"
    return f"{nbytes:.1f} PB"


def compile_excludes(patterns: list[str]) -> list[re.Pattern]:
    """编译排除正则列表。"""
    return [re.compile(p) for p in patterns if p]


def is_excluded(name: str, compiled: list[re.Pattern]) -> bool:
    return any(p.match(name) for p in compiled)


# ── 目录统计（递归）───────────────────────────────────────────

def count_dir(dir_path: Path, compiled: list[re.Pattern]) -> tuple[int, int]:
    """递归统计目录内文件数和总大小。返回 (file_count, total_size)。

    跳过编译后正则匹配到的目录及其后代。
    """
    t0 = time.time()
    fc, ts = 0, 0
    try:
        for f in dir_path.rglob("*"):
            # 跳过排除目录及其后代
            if any(is_excluded(p.name, compiled) for p in f.parents if p != dir_path):
                continue
            try:
                if f.is_file() and not f.is_symlink():
                    try:
                        fc += 1
                        ts += f.stat().st_size
                    except OSError:
                        pass
            except OSError:
                pass
    except (PermissionError, OSError):
        pass
    elapsed = time.time() - t0
    if elapsed > 1.0:
        from meta_store.logger import debug
        debug(f"count_dir({dir_path.name}): {fc} files, {elapsed:.1f}s")
    return fc, ts


# ── 目录树构建 ────────────────────────────────────────────────

def build_tree(
    root: Path,
    compiled: list[re.Pattern],
    max_depth: int,
    fields: set,
    show_files: bool,
    current_depth: int = 0,
) -> list[dict] | None:
    """递归构建目录节点列表。"""

    if max_depth >= 0 and current_depth > max_depth:
        return None

    try:
        entries = sorted(
            root.iterdir(),
            key=lambda e: (not e.is_dir(), e.name.lower()),
        )
    except (PermissionError, OSError):
        return None

    items: list[dict] = []

    for entry in entries:
        if is_excluded(entry.name, compiled):
            continue

        # 判断类型前先捕获异常（长路径/权限/特殊文件）
        try:
            is_dir = entry.is_dir()
            is_file = entry.is_file()
            is_sym = entry.is_symlink()
        except OSError:
            continue

        try:
            st = entry.stat()
        except OSError:
            continue

        if is_dir and not is_sym:
            children = build_tree(
                entry, compiled, max_depth, fields, show_files, current_depth + 1,
            )

            node: dict = {
                "name": entry.name,
                "type": "dir",
                "des": "",
            }

            need_fc = "file_count" in fields
            need_ts = "total_size" in fields or "total_size_human" in fields
            if need_fc or need_ts:
                fc, ts = count_dir(entry, compiled)
                if need_fc:
                    node["file_count"] = fc
                if "total_size" in fields:
                    node["total_size"] = ts
                if "total_size_human" in fields:
                    node["total_size_human"] = format_size(ts)

            if "modified" in fields:
                node["modified"] = datetime.fromtimestamp(st.st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                )
            if "created" in fields:
                try:
                    node["created"] = datetime.fromtimestamp(st.st_ctime).strftime(
                        "%Y-%m-%d %H:%M"
                    )
                except OSError:
                    pass

            if children:
                node["items"] = children

            items.append(node)

        elif is_file and not is_sym and show_files:
            node = {
                "name": entry.name,
                "type": "file",
                "des": "",
            }

            if "size" in fields:
                node["size"] = st.st_size
            if "size_human" in fields:
                node["size_human"] = format_size(st.st_size)
            if "modified" in fields:
                node["modified"] = datetime.fromtimestamp(st.st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                )
            if "created" in fields:
                try:
                    node["created"] = datetime.fromtimestamp(st.st_ctime).strftime(
                        "%Y-%m-%d %H:%M"
                    )
                except OSError:
                    pass

            items.append(node)

    return items if items else None


# ── des 合并逻辑 ──────────────────────────────────────────────

def flatten_des(tree: list[dict], parent_path: str = "") -> dict[str, str]:
    """从已有树中提取所有非空 des 映射 {相对路径: des}。"""
    result: dict[str, str] = {}
    for item in tree:
        full_path = f"{parent_path}/{item['name']}" if parent_path else item["name"]
        des = item.get("des", "").strip()
        if des:
            result[full_path] = des
        if "items" in item:
            result.update(flatten_des(item["items"], full_path))
    return result


def merge_des(tree: list[dict], des_map: dict[str, str], parent_path: str = ""):
    """将已保存的 des 值合并回新树。只覆盖 des 为空的节点。"""
    for item in tree:
        full_path = f"{parent_path}/{item['name']}" if parent_path else item["name"]
        if full_path in des_map and not item.get("des", "").strip():
            item["des"] = des_map[full_path]
        if "items" in item:
            merge_des(item["items"], des_map, full_path)


# ── 扫描入口 ──────────────────────────────────────────────────

def scan_path(
    target: Path,
    depth: int = -1,
    fields_str: str = "size,size_human,modified,file_count,total_size_human",
    exclude_patterns: list[str] | None = None,
    dirs_only: bool = False,
) -> dict:
    """扫描路径，返回完整 meta 节点（含根）。

    exclude_patterns: 正则列表，默认 ["^\\..*"]（隐藏文件）。
    """
    if not target.is_dir():
        raise NotADirectoryError(f"'{target}' 不是有效目录")

    patterns = exclude_patterns or [r"^\..*"]
    compiled = compile_excludes(patterns)

    selected_fields: set[str] = set()
    for f in fields_str.split(","):
        f = f.strip()
        if f in AVAILABLE_FIELDS:
            selected_fields.add(f)

    show_files = not dirs_only
    new_items = build_tree(target, compiled, depth, selected_fields, show_files) or []

    root_node: dict = {
        "name": target.name,
        "type": "dir",
        "des": "",
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if new_items:
        root_node["items"] = new_items

    if "file_count" in selected_fields or "total_size" in selected_fields or "total_size_human" in selected_fields:
        fc, ts = count_dir(target, compiled)
        if "file_count" in selected_fields:
            root_node["file_count"] = fc
        if "total_size" in selected_fields:
            root_node["total_size"] = ts
        if "total_size_human" in selected_fields:
            root_node["total_size_human"] = format_size(ts)

    return root_node


def merge_des_from_tree(new_tree: dict, old_tree: dict | None) -> dict:
    """从旧树提取 des 映射，合并到新树。返回新树（含保留的 des）。"""
    if not old_tree:
        return new_tree

    # 根节点 des
    old_root_des = old_tree.get("des", "").strip()
    if old_root_des and not new_tree.get("des", "").strip():
        new_tree["des"] = old_root_des

    # 子节点 des
    old_items = old_tree.get("items", [])
    new_items = new_tree.get("items", [])
    if old_items and new_items:
        des_map = flatten_des(old_items)
        merge_des(new_items, des_map)

    return new_tree


# ── 跨 entry des 同步 ──────────────────────────────────────────

def _path_sep(base: str) -> str:
    """根据路径风格返回分隔符。"""
    return "\\" if "\\" in base else "/"


def _collect_des_recursive(items: list[dict], parent_abs: str, index: dict):
    """递归收集 绝对路径→des（仅非空）。"""
    sep = _path_sep(parent_abs)
    for item in items:
        abs_path = parent_abs + sep + item["name"]
        des = (item.get("des") or "").strip()
        if des:
            index[abs_path] = des
        if "items" in item:
            _collect_des_recursive(item["items"], abs_path, index)


def _apply_des_recursive(items: list[dict], parent_abs: str, index: dict):
    """递归应用 des 索引到 tree 节点。"""
    sep = _path_sep(parent_abs)
    for item in items:
        abs_path = parent_abs + sep + item["name"]
        if abs_path in index:
            item["des"] = index[abs_path]
        if "items" in item:
            _apply_des_recursive(item["items"], abs_path, index)


def sync_des_across_entries(store: dict, saved_path: str):
    """保存某 entry 后，将其 des 同步到所有其他 entry 的对应节点。

    场景：扫描了 D:\\project 和 D:\\project\\llm-plan，
    在 D:\\project 的 tree 里编辑 llm-plan 子节点 des = "工具"，
    保存后 D:\\project\\llm-plan entry 的根 des 也应变为 "工具"，反之亦然。
    """
    saved_entry = store.get("paths", {}).get(saved_path)
    if not saved_entry or not saved_entry.get("tree"):
        return

    saved_tree = saved_entry["tree"]

    # 1. 构建本次保存的 des 索引（绝对路径→des，仅非空）
    saved_index: dict[str, str] = {}
    root_des = (saved_tree.get("des") or "").strip()
    if root_des:
        saved_index[saved_path] = root_des
    _collect_des_recursive(saved_tree.get("items", []), saved_path, saved_index)

    if not saved_index:
        return

    # 2. 应用到所有 entry（含自身，确保一致性）
    for path_key, entry in store.get("paths", {}).items():
        tree = entry.get("tree")
        if not tree:
            continue
        # 根节点
        if path_key in saved_index:
            tree["des"] = saved_index[path_key]
            entry["des"] = saved_index[path_key]
        # 子节点
        _apply_des_recursive(tree.get("items", []), path_key, saved_index)


# ── meta 文件读写 ──────────────────────────────────────────────

def load_meta(fp: Path) -> dict | None:
    """加载已有 meta 文件，返回根节点或 None。"""
    if not fp.exists():
        return None
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "name" in data:
            return data
        return None
    except (json.JSONDecodeError, OSError):
        return None


def save_meta(fp: Path, data: dict):
    """原子写入 meta 文件。"""
    fp.parent.mkdir(parents=True, exist_ok=True)
    tmp = fp.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(str(tmp), str(fp))
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise
