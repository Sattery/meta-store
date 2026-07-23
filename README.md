# Meta Store

> 目录树元数据管理工具。扫描目录 → 编辑描述 → 集中管理。

为任意目录生成目录树结构，用于给每个文件/文件夹标注用途描述，所有数据集中存储在一个 JSON 文件中。

## 快速开始

### 打包版

下载 `meta-store.exe`，双击运行。零依赖、零窗口、便携。

托盘出现蓝色 **M** 图标 → 浏览器自动打开 → 输入路径开始扫描。

### 使用

```bash
# 双击 tray.bat（首次自动安装依赖）
# 或 CLI：
python meta-store.py scan <路径>     # 扫描
python meta-store.py list            # 列出
python meta-store.py show [路径]     # 查看
python meta-store.py view            # 浏览器可视化
```

### 桌面 GUI

```bash
双击 gui.bat    # 原生窗口（需要 customtkinter）
```

## 配置

默认存储位置：`.metastore/`（隐藏目录）。可通过托盘右键「打开配置」或网页 ⚙️ 按钮自定义。
