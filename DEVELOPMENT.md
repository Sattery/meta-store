# Meta Store — 目录树元数据管理器

> **v0.3** — 系统托盘常驻 + 浏览器编辑器，CLI / View 零依赖。

为任意目录生成完整目录树结构，集中存储、可视化管理。核心流程：**输入路径 → 扫描目录树 → 编辑每个文件/文件夹的描述 → 保存到集中存储**。

提供四种使用方式：**系统托盘**（推荐，静默常驻 + 浏览器操作）、**浏览器编辑器**（HTTP server + HTML）、**桌面 GUI**（customtkinter 原生窗口）、**CLI**（命令行）。

---

## 目录结构

```
gen-meta/
├── gen_meta/                 # Python 包
│   ├── __init__.py
│   ├── scanner.py            # 核心扫描 + des 合并 + 跨 entry 同步
│   ├── store.py              # 存储读写 + 备份策略
│   ├── server.py             # HTTP 服务端（API: scan/save/store/remove）
│   ├── tray.py               # 系统托盘常驻（pystray + 后台 server）
│   └── gui.py                # 桌面 GUI（customtkinter，可选）
├── static/
│   └── editor.html           # 可视化编辑器（浏览器主入口）
├── .metastore/               # exe 运行时数据（隐藏目录，gitignored）
│   └── .gitkeep
├── data/                     # 源码运行时数据（gitignored）
│   └── .gitkeep
├── gen-meta.py               # CLI 工具入口（scan/list/show/view/remove/gui）
├── gen-meta.bat              # Windows CLI 包装（交互式或传参）
├── tray.bat                  # 开发者启动托盘（需要 venv，首次装依赖）
├── start.bat                 # 浏览器编辑器（server + 浏览器，有控制台）
├── gui.bat                   # 开发者启动 GUI（需要 venv，首次装依赖）
├── meta-store.spec           # PyInstaller 打包配置
├── dist/                     # 构建产物（gitignored）
│   └── meta-store.exe        # 单文件可执行程序（~20MB，零依赖）
├── requirements.txt          # 依赖声明（pystray / Pillow / customtkinter）
├── .gitignore
└── README.md
```

---

## 快速开始

### 打包版（推荐 — 零依赖零窗口）

```bash
# 双击 dist/meta-store.exe 即可（无需 Python 环境）
# 打包命令（开发者）：
pyinstaller meta-store.spec
```

> `.exe` 包含完整 Python 运行时 + 所有依赖，单个文件、零窗口、便携分发。

双击 `meta-store.exe` → 托盘蓝色 **M** 图标 → 浏览器自动打开编辑器。右键退出，进程同步释放。

### 开发版 — 系统托盘

```bash
# 双击 tray.bat（首次自动装依赖）
python gen_meta/tray.py
```

无黑窗口，与打包版体验一致。需要 Python 3.10+ 和 venv。

**托盘右键菜单：**
| 菜单项 | 说明 |
|---|---|
| 📂 打开编辑器 | 重新打开浏览器页面（默认项，双击图标同效） |
| ❌ 退出 | 停止 HTTP 服务并退出托盘 |

### 浏览器编辑器（带控制台）

```bash
# Windows: 双击 start.bat
# 或命令行：
python -m gen_meta.server
```

浏览器自动打开 → 输入目录路径 → 扫描 → 点击 `des` 填写描述 → `Ctrl+S` 保存。

**核心操作：**
| 操作 | 说明 |
|---|---|
| 📝 输入路径 | 顶栏输入或点击 📂 浏览文件夹 |
| 🔍 扫描 | 点击扫描按钮，目录树写入 `.metastore/meta-store.json` |
| 📁 路径列表 | 左侧已扫描路径，可展开子目录树，🔍 逐个扫描子目录 |
| ✏️ 编辑 des | 右侧树中直接点击描述列，内联编辑 |
| 💾 保存 | `Ctrl+S` 或点击底栏"保存 des"，自动跨 entry 同步 |
| 🔍 搜索 | 内容区搜索框过滤文件名和描述 |

### 桌面 GUI（可选）

```bash
# 双击 gui.bat（首次自动安装依赖）
python gen-meta.py gui
```

> 依赖 `customtkinter`，首次请双击 `gui.bat` 安装。

原生桌面窗口，零 HTTP 依赖。路径输入 → 扫描 → 展开目录树 → 内联编辑 des → 保存。

### CLI 模式

```bash
# 扫描目录 → 添加到集中存储
python gen-meta.py scan /path/to/project
python gen-meta.py scan /path/to/project -d 3 --dirs-only

# 列出所有已扫描路径
python gen-meta.py list

# 显示目录树
python gen-meta.py show                          # 显示所有
python gen-meta.py show D:\project\my-app       # 显示指定路径

# 移除路径
python gen-meta.py remove D:\project\my-app

# 浏览器可视化查看（无需服务端！）
python gen-meta.py view                          # 所有路径的可视化页面
python gen-meta.py view D:\project\my-app       # 只看指定路径

# 启动桌面 GUI
python gen-meta.py gui
```

**交互模式**：双击 `gen-meta.bat`，提示输入路径后自动执行 `scan`。

`gen-meta.py` 与可视化编辑器共享 `.metastore/meta-store.json` 存储，CLI 扫描的路径在浏览器中同样可见。

---

## 存储结构

数据文件存储位置取决于运行方式，可通过配置自定义：

| 运行方式 | 默认数据位置 |
|---|---|
| **打包 .exe** | `exe 同目录 / .metastore /`（隐藏目录） |
| **源码环境** | `gen-meta / data /` |

> exe 用 `.metastore` 隐藏目录避免污染，源码环境保持 `data/` 直观可见。

```json
{
  "version": 1,
  "updated_at": "2026-07-21 14:00:00",
  "paths": {
    "D:\\project\\tool-factory": {
      "path": "D:\\project\\tool-factory",
      "name": "tool-factory",
      "des": "工具工厂项目",
      "scanned_at": "2026-07-21 12:00",
      "scan_config": { "depth": 2, "fields": "...", "exclude": "..." },
      "tree": {
        "name": "tool-factory",
        "type": "dir",
        "des": "",
        "scan_time": "2026-07-21 12:00:00",
        "items": [
          { "name": "gen-meta", "type": "dir", "des": "元数据生成工具", "items": [...] },
          { "name": "llm-plan", "type": "dir", "des": "LLM 方案对比", "items": [...] }
        ]
      }
    }
  }
}
```

**跨路径 des 同步**：在父目录 tree 中编辑子目录节点的 des，保存后自动同步到子目录独立 entry 的根 des，反之亦然。

**备份策略**：每次保存前，当前 `meta-store.json` 自动改为 `meta-store.json.bak`（保留 1 份历史）。若写入失败则自动从 `.bak` 恢复。

---

## API

服务端提供 HTTP 接口，供 `editor.html` 通过 `fetch` 调用：

| 端点 | 方法 | Body | 说明 |
|---|---|---|---|
| `GET /` | GET | — | 返回可视化编辑器页面 |
| `GET /api/store` | GET | — | 获取完整 `meta-store.json` |
| `GET /api/paths` | GET | — | 获取所有已扫描路径列表 |
| `POST /api/scan` | POST | `{path, depth, fields, exclude, dirs_only}` | 扫描路径并写入存储 |
| `POST /api/save` | POST | `{path, tree}` | 保存 tree（含 des）并跨 entry 同步 |
| `POST /api/remove` | POST | `{path}` | 从存储中移除路径 |

---

## 可选字段

扫描时可选择附加到每个文件/目录节点的统计字段：

| 字段名 | 说明 | 节点类型 |
|---|---|---|
| `size` | 文件大小（字节） | file |
| `size_human` | 文件大小可读格式 | file |
| `modified` | 最后修改时间 | dir / file |
| `created` | 创建时间 | dir / file |
| `file_count` | 递归文件总数 | dir |
| `total_size` | 递归文件总大小（字节） | dir |
| `total_size_human` | 递归文件总大小可读格式 | dir |

默认：`size,modified,file_count,total_size_human`

---

## 架构

```
                   ┌─ tray.py (pystray 托盘)
                   │   └─ 后台线程: HTTPServer
                   │   └─ 右键菜单: 打开/退出
                   │
editor.html ──fetch──► gen_meta/server.py (HTTP :8765)
(浏览器)                 ├── /api/scan
                         ├── /api/save
                         ├── /api/store
                         └── /api/remove
                                │
                                ▼
                         gen_meta/scanner.py  ←── core engine
                         ├── build_tree()
                         ├── scan_path()
                         ├── merge_des_from_tree()
                         └── sync_des_across_entries()
                                │
                                ▼
                         gen_meta/store.py (I/O + backup)
                         ├── load_store()
                         └── save_store()  →  .metastore/meta-store.json
                                              .metastore/meta-store.json.bak

CLI: gen-meta.py  →  scanner + store  (共享同一存储)
GUI: gui.py       →  scanner + store  (customtkinter 原生窗口)
```

---

## 未来计划

- **v0.4** — 导出功能（JSON 摘要 / Markdown 目录树）
- **v0.5** — 托盘图标状态指示（服务运行/扫描中）

---

## 环境要求

| 模式 | 依赖 | 说明 |
|---|---|---|
| **打包 .exe** | 零依赖 | 单文件 ~20MB，含完整 Python 运行时 |
| **CLI / Server / View** | 零第三方依赖 | 仅 Python 标准库 |
| **开发版托盘** | pystray + Pillow | `tray.bat` 自动安装 |
| **桌面 GUI** | customtkinter | `gui.bat` 自动安装 |
| **浏览器** | 任意现代浏览器 | 托盘 / Server / View 模式 |

---

## 变更日志

### v0.3.1 (2026-07-22)

- **PyInstaller 打包**：一键生成 `dist/meta-store.exe`
  - `--onefile --noconsole`：单文件、零窗口、零依赖
  - 自动包含 `static/editor.html` 数据文件，`_MEIPASS` 路径天然对齐无需改代码
  - `meta-store.spec` 保存打包配置，可复现构建
- 删除 `tray.vbs` / `gui.vbs`（`.exe` 替代）

### v0.3 (2026-07-22)

- **系统托盘常驻**（pystray）：双击 `tray.vbs` 零黑窗口静默启动
  - 后台线程运行 HTTP Server，浏览器自动打开编辑器
  - 右键菜单：打开编辑器 / 退出；进程同步释放，端口清理
  - 单实例检测：端口已占用时只开浏览器，不重复启动
  - 程序化生成托盘图标（蓝色圆角 M），不依赖外部图片资源
- `tray.vbs` + `gui.vbs`：VBScript 包装 `pythonw.exe`，真正零窗口启动
  - `tray.bat` / `gui.bat` 作为首次安装脚本（有控制台，显示安装进度）
- `requirements.txt`：新增 pystray / Pillow 依赖声明

### v0.2 (2026-07-22)

- **桌面 GUI**（customtkinter）：原生窗口、路径侧栏、目录树展开折叠、内联 des 编辑、搜索、跨 entry 同步
- `gui.bat` 首次运行自动安装依赖（uv venv + pip install）
- `gen-meta.py gui` 子命令
- `gen_meta/store.py` 独立存储模块 + 1 份备份策略
- `gen-meta.py view` 子命令：零服务端浏览器可视化
- `requirements.txt` 依赖声明

### v0.1 (2026-07-21)

- 目录结构重构：`gen_meta/` Python 包、`static/` 前端、`scripts/` 脚本
- 可视化编辑器（HTML）：路径管理、目录树展示、内联 des 编辑、搜索、跨 entry 同步
- CLI 模式：`gen-meta.py` 命令行扫描
- 集中存储：`data/meta-store.json`
- Git 版本管理初始化
