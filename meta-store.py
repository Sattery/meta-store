#!/usr/bin/env python3
"""meta-store CLI — 目录树元数据管理命令行工具。

与可视化编辑器共享 .metastore/meta-store.json 存储。
用法:
  python meta-store.py scan <路径>   扫描目录并添加到集中存储
  python meta-store.py list          列出所有已扫描路径
  python meta-store.py show [路径]   显示目录树
  python meta-store.py remove <路径> 从存储中移除路径
"""

import sys
from pathlib import Path

from meta_store.scanner import scan_path, merge_des_from_tree
from meta_store.store import load_store, save_store, list_paths, STORE_FILE, DATA_DIR


def _err(msg: str):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def _ensure_encoding():
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "buffer"):
                stream.reconfigure(encoding="utf-8")


# ── scan ──────────────────────────────────────────────────────

def cmd_scan(args):
    target = Path(args.path).resolve()
    if not target.is_dir():
        _err(f"'{args.path}' is not a valid directory")

    store = load_store()
    key = str(target)
    old_tree = store.get("paths", {}).get(key, {}).get("tree")

    print(f"Scanning: {key}")
    if args.exclude:
        exclude_pats = [n.strip() for n in args.exclude.split(",") if n.strip()]
    else:
        from meta_store.config import load_config
        exclude_pats = load_config().get("exclude_patterns", [r"^\..*"])
    new_tree = scan_path(
        target,
        depth=args.depth,
        fields_str=args.fields,
        exclude_patterns=exclude_pats,
        dirs_only=args.dirs_only,
    )
    new_tree = merge_des_from_tree(new_tree, old_tree)

    store.setdefault("paths", {})[key] = {
        "path": key,
        "name": target.name,
        "des": new_tree.get("des", ""),
        "scanned_at": new_tree.get("scan_time", ""),
        "scan_config": {
            "depth": args.depth,
            "fields": args.fields,
            "exclude": args.exclude or "",
            "dirs_only": args.dirs_only,
        },
        "tree": new_tree,
    }
    save_store(store)

    # 统计
    def _count(tree, t):
        n = sum(1 for i in tree if i.get("type") == t)
        for i in tree:
            if "items" in i:
                n += _count(i["items"], t)
        return n

    items = new_tree.get("items", [])
    print(f"  dirs: {_count(items, 'dir')}, files: {_count(items, 'file')}")
    print(f"  saved to {STORE_FILE}")


# ── list ──────────────────────────────────────────────────────

def cmd_list(args):
    store = load_store()
    paths = sorted(store.get("paths", {}).items())
    if not paths:
        print("(empty — no paths scanned yet)")
        return
    for key, entry in paths:
        name = entry.get("name", key)
        des = entry.get("des", "")
        when = entry.get("scanned_at", "")
        tag = f"  # {des}" if des else ""
        print(f"  {name:<30s} {when:>16s}{tag}")
        print(f"    {key}")


# ── show ──────────────────────────────────────────────────────

def _print_tree(node, prefix="", is_last=True, show_des=True):
    """递归打印目录树。"""
    connector = "└── " if is_last else "├── "
    icon = "📂" if node.get("type") == "dir" else "📄"
    line = f"{prefix}{connector}{icon} {node['name']}"
    if show_des and node.get("des"):
        line += f"  — {node['des']}"
    print(line)

    children = node.get("items", [])
    for i, child in enumerate(children):
        child_prefix = prefix + ("    " if is_last else "│   ")
        _print_tree(child, child_prefix, i == len(children) - 1, show_des)


def cmd_show(args):
    store = load_store()
    paths = store.get("paths", {})

    if args.path:
        key = str(Path(args.path).resolve())
        if key not in paths:
            _err(f"path not found: {key}\n       use 'list' to see stored paths")
        tree = paths[key].get("tree")
        if not tree:
            _err("no tree data for this path")
        print(f"\n{key}")
        children = tree.get("items", [])
        for i, child in enumerate(children):
            _print_tree(child, "", i == len(children) - 1)
        return

    # 无参：列出所有路径，让用户选
    if not paths:
        print("(empty — no paths scanned yet)")
        return
    for key, entry in sorted(paths.items()):
        name = entry.get("name", key)
        tree = entry.get("tree")
        if not tree:
            print(f"\n{key}\n  (no tree data)")
            continue
        print(f"\n{key}")
        children = tree.get("items", [])
        for i, child in enumerate(children):
            _print_tree(child, "", i == len(children) - 1)


# ── view ──────────────────────────────────────────────────────

EDITOR_HTML = Path(__file__).resolve().parent / "static" / "editor.html"


def cmd_view(args):
    """将 meta-store.json 数据注入 editor.html，直接浏览器渲染（零服务端）。"""
    import json
    import webbrowser

    store = load_store()

    # 过滤：指定路径则只保留该路径
    if args.path:
        key = str(Path(args.path).resolve())
        if key not in store.get("paths", {}):
            _err(f"path not found: {key}\n       use 'list' to see stored paths")
        view_store = {"version": store["version"], "paths": {key: store["paths"][key]}}
    else:
        view_store = store

    if not view_store.get("paths"):
        _err("no paths to display")

    # 读模板，注入数据
    template = EDITOR_HTML.read_text(encoding="utf-8")
    data_json = json.dumps(view_store, indent=2, ensure_ascii=False)
    injection = f"window.EMBEDDED_STORE = {data_json};"

    marker = "EMBEDDED_STORE 由 meta-store.py view 注入"
    idx = template.find(marker)
    if idx == -1:
        _err("editor.html missing embedded view marker")
    line_end = template.index("\n", idx)
    html = template[:line_end + 1] + injection + "\n" + template[line_end + 1:]

    # 写入 .metastore/view.html（项目本地，每次覆盖）
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "view.html"
    out.write_text(html, encoding="utf-8")
    print(f"Written: {out}")
    webbrowser.open(f"file:///{out.as_posix()}")


# ── gui ───────────────────────────────────────────────────────

def cmd_gui(args):
    """启动桌面 GUI（customtkinter）。"""
    try:
        from meta_store.gui import main
    except ImportError as e:
        _err(
            f"GUI 依赖未安装: {e}\n"
            "       运行: uv pip install customtkinter\n"
            "       或:   pip install customtkinter"
        )
    main()


# ── remove ────────────────────────────────────────────────────

def cmd_remove(args):
    key = str(Path(args.path).resolve())
    store = load_store()
    if key not in store.get("paths", {}):
        _err(f"path not found: {key}")
    del store["paths"][key]
    save_store(store)
    print(f"Removed: {key}")


# ── main ──────────────────────────────────────────────────────

def main():
    _ensure_encoding()

    import argparse
    p = argparse.ArgumentParser(
        description="Meta Store CLI — 目录树元数据管理",
    )
    sub = p.add_subparsers(dest="command", help="subcommand")

    # scan
    sp = sub.add_parser("scan", help="scan a directory into store")
    sp.add_argument("path", help="directory path to scan")
    sp.add_argument("-d", "--depth", type=int, default=2, help="scan depth (default: 2)")
    sp.add_argument("--fields", default="size,modified,file_count,total_size_human",
                    help="fields to include")
    sp.add_argument("-e", "--exclude", default=None,
                    help="extra dirs to exclude (comma-separated)")
    sp.add_argument("--dirs-only", action="store_true", help="only directories")
    sp.set_defaults(func=cmd_scan)

    # list
    lp = sub.add_parser("list", help="list all stored paths")
    lp.set_defaults(func=cmd_list)

    # show
    shp = sub.add_parser("show", help="show directory tree")
    shp.add_argument("path", nargs="?", default=None, help="path to show (omit for all)")
    shp.set_defaults(func=cmd_show)

    # view
    vp = sub.add_parser("view", help="open visual tree in browser (no server)")
    vp.add_argument("path", nargs="?", default=None, help="path to view (omit for all)")
    vp.set_defaults(func=cmd_view)

    # remove
    rp = sub.add_parser("remove", help="remove a path from store")
    rp.add_argument("path", help="path to remove")
    rp.set_defaults(func=cmd_remove)

    # gui
    gp = sub.add_parser("gui", help="launch desktop GUI (customtkinter)")
    gp.set_defaults(func=cmd_gui)

    args = p.parse_args()
    if not args.command:
        p.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
