"""gui.py — Meta Store 桌面 GUI（customtkinter）。

零 HTTP 依赖，原生桌面窗口。
直接调用 meta_store.scanner + meta_store.store 模块，与 CLI / server 共享存储。
"""

import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from meta_store.scanner import (
    scan_path,
    merge_des_from_tree,
    sync_des_across_entries,
)
from meta_store.store import load_store, save_store

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


class MetaStoreGUI(ctk.CTk):
    """Meta Store 主窗口。"""

    def __init__(self):
        super().__init__()

        self.title("Meta Store — 目录树元数据管理")
        self.geometry("1200x750")
        self.minsize(900, 600)

        # 状态
        self.store = load_store()
        self.current_path: str | None = None
        self.current_tree: dict | None = None
        self.node_widgets: dict = {}  # node_path → widget info
        self.dirty = False

        self._setup_ui()
        self._refresh_sidebar()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI 布局 ─────────────────────────────────────────────────

    def _setup_ui(self):
        # ── 顶栏 ──
        self.toolbar = ctk.CTkFrame(self, height=52)
        self.toolbar.pack(side="top", fill="x")
        self.toolbar.pack_propagate(False)

        self.path_entry = ctk.CTkEntry(
            self.toolbar,
            placeholder_text="输入路径或点击浏览...",
            height=32,
        )
        self.path_entry.pack(side="left", padx=(12, 4), pady=10, fill="x", expand=True)
        self.path_entry.bind("<Return>", lambda e: self._do_scan())

        self.browse_btn = ctk.CTkButton(
            self.toolbar, text="📁", width=36, height=32,
            command=self._browse_folder,
        )
        self.browse_btn.pack(side="left", padx=2, pady=10)

        self.scan_btn = ctk.CTkButton(
            self.toolbar, text="🔍 扫描", width=80, height=32,
            command=self._do_scan,
        )
        self.scan_btn.pack(side="left", padx=2, pady=10)

        self.settings_btn = ctk.CTkButton(
            self.toolbar, text="⚙️", width=36, height=32,
            command=self._toggle_settings,
        )
        self.settings_btn.pack(side="left", padx=(2, 12), pady=10)

        # 右侧
        self.save_btn = ctk.CTkButton(
            self.toolbar, text="💾 保存", width=80, height=32,
            command=self._do_save,
            fg_color="#2E7D32", hover_color="#1B5E20",
        )
        self.save_btn.pack(side="right", padx=(2, 12), pady=10)

        self.search_entry = ctk.CTkEntry(
            self.toolbar, placeholder_text="🔍 搜索...", width=150, height=32,
        )
        self.search_entry.pack(side="right", padx=2, pady=10)
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # ── 设置面板（默认隐藏）──
        self.settings_frame = ctk.CTkFrame(self, height=44)

        ctk.CTkLabel(self.settings_frame, text="深度:").pack(
            side="left", padx=(12, 4), pady=10
        )
        self.depth_var = ctk.StringVar(value="2")
        ctk.CTkOptionMenu(
            self.settings_frame, variable=self.depth_var,
            values=["1", "2", "3", "4", "5", "全部"],
            width=90, height=28,
        ).pack(side="left", padx=2, pady=10)

        self.dirs_only_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self.settings_frame, text="仅目录", variable=self.dirs_only_var,
            height=28,
        ).pack(side="left", padx=12, pady=10)

        ctk.CTkLabel(self.settings_frame, text="额外排除:").pack(
            side="left", padx=(12, 4), pady=10
        )
        self.exclude_entry = ctk.CTkEntry(
            self.settings_frame, placeholder_text="dir1,dir2", width=150, height=28,
        )
        self.exclude_entry.pack(side="left", padx=2, pady=10)

        # ── 主体：左 + 右 ──
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(side="top", fill="both", expand=True)

        # 侧栏
        self.sidebar = ctk.CTkFrame(self.body, width=250)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self.sidebar, text="已扫描路径",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="top", padx=12, pady=(12, 6))

        self.sidebar_scroll = ctk.CTkScrollableFrame(self.sidebar)
        self.sidebar_scroll.pack(side="top", fill="both", expand=True, padx=4, pady=(0, 4))

        # 主区域
        self.main_area = ctk.CTkFrame(self.body)
        self.main_area.pack(side="left", fill="both", expand=True)

        # 内容头
        self.content_header = ctk.CTkFrame(self.main_area, height=44)
        self.content_header.pack(side="top", fill="x")
        self.content_header.pack_propagate(False)

        self.path_label = ctk.CTkLabel(
            self.content_header, text="（选择左侧路径或扫描新路径）",
            font=ctk.CTkFont(size=13), anchor="w",
        )
        self.path_label.pack(side="left", padx=12, pady=10, fill="x", expand=True)

        ctk.CTkLabel(
            self.content_header, text="根描述:",
            font=ctk.CTkFont(size=12), text_color="gray50",
        ).pack(side="right", padx=(0, 4), pady=10)

        self.root_des_entry = ctk.CTkEntry(
            self.content_header, placeholder_text="...", width=250, height=28,
        )
        self.root_des_entry.pack(side="right", padx=(0, 12), pady=8)
        self.root_des_entry.bind("<KeyRelease>", lambda e: self._set_dirty(True))

        # 树区域
        self.tree_scroll = ctk.CTkScrollableFrame(self.main_area, fg_color="transparent")
        self.tree_scroll.pack(side="top", fill="both", expand=True, padx=4, pady=4)

        # ── 状态栏 ──
        self.statusbar = ctk.CTkFrame(self, height=28)
        self.statusbar.pack(side="bottom", fill="x")
        self.statusbar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.statusbar, text="就绪",
            font=ctk.CTkFont(size=11), text_color="gray50",
        )
        self.status_label.pack(side="left", padx=12, pady=4)

        self.stats_label = ctk.CTkLabel(
            self.statusbar, text="",
            font=ctk.CTkFont(size=11), text_color="gray50",
        )
        self.stats_label.pack(side="left", padx=24, pady=4)

        self.dirty_label = ctk.CTkLabel(
            self.statusbar, text="",
            font=ctk.CTkFont(size=11), text_color="#F44336",
        )
        self.dirty_label.pack(side="right", padx=12, pady=4)

    def _toggle_settings(self):
        if self.settings_frame.winfo_ismapped():
            self.settings_frame.pack_forget()
        else:
            self.settings_frame.pack(side="top", fill="x", before=self.body)

    def _browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder)

    # ── 状态 ───────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self.status_label.configure(text=msg)

    def _set_dirty(self, dirty: bool = True):
        self.dirty = dirty
        self.dirty_label.configure(text="● 已修改" if dirty else "")

    def _update_stats(self):
        if not self.current_tree:
            self.stats_label.configure(text="")
            return

        def _count(node, t):
            n = sum(1 for i in node.get("items", []) if i.get("type") == t)
            for i in node.get("items", []):
                if "items" in i:
                    n += _count(i, t)
            return n

        dirs = _count(self.current_tree, "dir")
        files = _count(self.current_tree, "file")
        self.stats_label.configure(text=f"📁 {dirs}  📄 {files}")

    # ── 侧栏 ───────────────────────────────────────────────────

    def _refresh_sidebar(self):
        for w in self.sidebar_scroll.winfo_children():
            w.destroy()

        paths = sorted(self.store.get("paths", {}).keys())
        if not paths:
            ctk.CTkLabel(
                self.sidebar_scroll, text="暂无路径\n使用顶部输入扫描",
                text_color="gray50", justify="center",
            ).pack(pady=40)
            return

        for path_key in paths:
            entry = self.store["paths"][path_key]
            name = entry.get("name", path_key)
            des = entry.get("des", "")

            item = ctk.CTkFrame(self.sidebar_scroll, fg_color="transparent")
            item.pack(fill="x", padx=2, pady=2)

            row = ctk.CTkFrame(item, fg_color="transparent")
            row.pack(fill="x")

            btn = ctk.CTkButton(
                row, text=name, anchor="w", height=30,
                command=lambda pk=path_key: self._select_path(pk),
            )
            btn.pack(side="left", fill="x", expand=True)

            del_btn = ctk.CTkButton(
                row, text="✕", width=28, height=30,
                fg_color="transparent", hover_color="#FFCDD2",
                text_color="#F44336",
                command=lambda pk=path_key: self._remove_path(pk),
            )
            del_btn.pack(side="left", padx=(2, 0))

            if des:
                ctk.CTkLabel(
                    item, text=f"  {des}", text_color="gray50",
                    font=ctk.CTkFont(size=11), anchor="w",
                ).pack(fill="x", padx=4)

    def _select_path(self, path_key: str):
        # flush 当前树到内存
        self._flush_current()

        self.current_path = path_key
        entry = self.store["paths"][path_key]
        self.current_tree = entry.get("tree")

        if not self.current_tree:
            self._set_status("无树数据")
            return

        self.path_label.configure(text=path_key)
        self.root_des_entry.delete(0, "end")
        self.root_des_entry.insert(0, self.current_tree.get("des", ""))

        self._render_tree(self.current_tree)
        self._update_stats()
        self._set_status(f"已加载: {path_key}")
        self._set_dirty(False)

    def _remove_path(self, path_key: str):
        if not messagebox.askyesno("删除", f"确定删除？\n{path_key}"):
            return
        del self.store["paths"][path_key]
        save_store(self.store)
        if self.current_path == path_key:
            self.current_path = None
            self.current_tree = None
            self._render_empty()
        self._refresh_sidebar()
        self._set_status("已删除")

    # ── 树渲染 ─────────────────────────────────────────────────

    def _render_empty(self):
        for w in self.tree_scroll.winfo_children():
            w.destroy()
        self.node_widgets = {}
        self.path_label.configure(text="（选择左侧路径或扫描新路径）")
        self.root_des_entry.delete(0, "end")
        self.stats_label.configure(text="")

    def _render_tree(self, tree_data: dict):
        for w in self.tree_scroll.winfo_children():
            w.destroy()
        self.node_widgets = {}

        items = tree_data.get("items", [])
        if not items:
            ctk.CTkLabel(
                self.tree_scroll, text="（空目录）", text_color="gray50",
            ).pack(pady=40)
            return

        for node in items:
            self._render_node(self.tree_scroll, node, "")

    def _render_node(self, parent, node: dict, parent_path: str):
        node_path = (
            (parent_path + "/" + node["name"]) if parent_path
            else ("/" + node["name"])
        )
        is_dir = node.get("type") == "dir"
        has_children = bool(node.get("items"))

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=1)

        # 展开/折叠按钮
        if has_children:
            expand_btn = ctk.CTkButton(
                row, text="▶", width=22, height=22,
                fg_color="transparent", hover_color=("gray80", "gray20"),
                font=ctk.CTkFont(size=10),
                command=lambda np=node_path: self._toggle_node(np),
            )
            expand_btn.pack(side="left", padx=(0, 2))
        else:
            ctk.CTkLabel(row, text="", width=22).pack(side="left")
            expand_btn = None

        # 图标
        icon = "📂" if is_dir else "📄"
        ctk.CTkLabel(row, text=icon, width=22).pack(side="left")

        # 名称
        name_font = ctk.CTkFont(size=13, weight="bold" if is_dir else "normal")
        ctk.CTkLabel(
            row, text=node["name"], anchor="w", width=160, font=name_font,
        ).pack(side="left", padx=(4, 8))

        # des 输入框
        des_entry = ctk.CTkEntry(
            row, placeholder_text="描述...", height=24,
        )
        des_entry.insert(0, node.get("des", ""))
        des_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        des_entry.bind("<KeyRelease>", lambda e: self._set_dirty(True))

        self.node_widgets[node_path] = {
            "node": node,
            "row": row,
            "parent": parent,
            "expand_btn": expand_btn,
            "des_entry": des_entry,
            "expanded": False,
            "children_frame": None,
        }

    def _toggle_node(self, node_path: str):
        info = self.node_widgets.get(node_path)
        if not info:
            return

        if info["expanded"]:
            # 折叠前收集子节点 des 到 node dict
            self._collect_children_des(info["node"], node_path)
            if info["children_frame"]:
                info["children_frame"].pack_forget()
                info["children_frame"].destroy()
                info["children_frame"] = None
                self._cleanup_child_widgets(node_path)
            info["expanded"] = False
            if info["expand_btn"]:
                info["expand_btn"].configure(text="▶")
        else:
            # 展开子节点
            children_frame = ctk.CTkFrame(info["parent"], fg_color="transparent")
            children_frame.pack(fill="x", padx=(24, 0), after=info["row"])
            for child in info["node"].get("items", []):
                self._render_node(children_frame, child, node_path)
            info["children_frame"] = children_frame
            info["expanded"] = True
            if info["expand_btn"]:
                info["expand_btn"].configure(text="▼")

    def _cleanup_child_widgets(self, parent_path: str):
        prefix = parent_path + "/"
        for k in list(self.node_widgets.keys()):
            if k.startswith(prefix):
                del self.node_widgets[k]

    def _collect_children_des(self, node: dict, parent_path: str):
        """递归收集子节点 des 到 node dict（折叠前调用）。"""
        for child in node.get("items", []):
            child_path = parent_path + "/" + child["name"]
            info = self.node_widgets.get(child_path)
            if info:
                child["des"] = info["des_entry"].get().strip()
            if "items" in child:
                self._collect_children_des(child, child_path)

    def _collect_des(self, node: dict, parent_path: str):
        """收集单个节点 + 递归子节点的 des 到 node dict。"""
        node_path = (
            (parent_path + "/" + node["name"]) if parent_path
            else ("/" + node["name"])
        )
        info = self.node_widgets.get(node_path)
        if info:
            node["des"] = info["des_entry"].get().strip()
        if "items" in node:
            for child in node["items"]:
                self._collect_des(child, node_path)

    def _flush_current(self):
        """将当前 UI 的 des 收集到内存中的 current_tree（不写文件）。"""
        if not self.current_path or not self.current_tree:
            return
        self.current_tree["des"] = self.root_des_entry.get().strip()
        for node in self.current_tree.get("items", []):
            self._collect_des(node, "")
        self.store["paths"][self.current_path]["tree"] = self.current_tree
        self.store["paths"][self.current_path]["des"] = self.current_tree.get("des", "")

    # ── 扫描 ───────────────────────────────────────────────────

    def _do_scan(self):
        path = self.path_entry.get().strip()
        if not path:
            self._set_status("请输入路径")
            return

        target = Path(path).resolve()
        if not target.is_dir():
            self._set_status(f"无效目录: {target}")
            return

        self._set_status("扫描中...")
        self.scan_btn.configure(state="disabled", text="扫描中...")

        depth_str = self.depth_var.get()
        depth = -1 if depth_str == "全部" else int(depth_str)
        dirs_only = self.dirs_only_var.get()
        exclude = self.exclude_entry.get().strip()

        # flush 当前修改到内存
        self._flush_current()

        def scan_thread():
            old_tree = self.store.get("paths", {}).get(str(target), {}).get("tree")
            new_tree = scan_path(
                target, depth=depth,
                fields_str="size,size_human,modified,file_count,total_size_human",
                exclude_patterns=exclude.split(",") if exclude else None,
                dirs_only=dirs_only,
            )
            new_tree = merge_des_from_tree(new_tree, old_tree)

            self.store.setdefault("paths", {})[str(target)] = {
                "path": str(target),
                "name": target.name,
                "des": new_tree.get("des", ""),
                "scanned_at": new_tree.get("scan_time", ""),
                "scan_config": {
                    "depth": depth,
                    "fields": "size,size_human,modified,file_count,total_size_human",
                    "exclude": exclude,
                    "dirs_only": dirs_only,
                },
                "tree": new_tree,
            }
            save_store(self.store)
            self.after(0, self._scan_done, str(target))

        threading.Thread(target=scan_thread, daemon=True).start()

    def _scan_done(self, path_key: str):
        self.scan_btn.configure(state="normal", text="🔍 扫描")
        self._refresh_sidebar()
        self._select_path(path_key)
        self._set_status("扫描完成")
        self._set_dirty(False)

    # ── 保存 ───────────────────────────────────────────────────

    def _do_save(self):
        if not self.current_path or not self.current_tree:
            self._set_status("无内容可保存")
            return

        self._flush_current()
        sync_des_across_entries(self.store, self.current_path)
        save_store(self.store)
        self._set_dirty(False)
        self._set_status(f"已保存: {self.current_path}")
        self._refresh_sidebar()

    # ── 搜索 ───────────────────────────────────────────────────

    def _on_search(self, event=None):
        query = self.search_entry.get().strip().lower()
        for _path, info in self.node_widgets.items():
            name = info["node"]["name"].lower()
            if query and query in name:
                info["row"].configure(fg_color=("gray80", "gray20"))
            else:
                info["row"].configure(fg_color="transparent")

    # ── 关闭 ───────────────────────────────────────────────────

    def _on_close(self):
        self._flush_current()
        if self.dirty:
            if messagebox.askyesno("退出", "有未保存的修改。保存后退出？"):
                self._do_save()
        self.destroy()


def main():
    """启动 GUI。"""
    app = MetaStoreGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
