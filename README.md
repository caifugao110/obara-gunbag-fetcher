# obara-gunbag-fetcher

*2D/3D文件批量获取与打包工具 — 根据文件清单从多个网络或本地源目录中查找 2D（DWG/PDF）和 3D（STEP/XT）文件，并将每个清单项打包为独立的 ZIP 压缩包。*

## 简介

**obara-gunbag-fetcher** 是一款基于 Python 的桌面 GUI 工具，专为 OBARA 有调图需求的人员打造，用于从多个网络或本地目录中快速查找 2D 和 3D 文件，并按清单逐项打包为 ZIP 压缩包。3D 部分继承自 [3d-batch-copy](https://github.com/caifugao110/3d-batch-copy)，新增 2D 文件获取与一键打包能力。

| 项目信息 | |
|---|---|
| 作者 | **Tobin** |
| 项目地址 | https://github.com/caifugao110/obara-gunbag-fetcher |
| 原始项目 | https://github.com/caifugao110/3d-batch-copy |
| 开源协议 | MIT |

## 功能特性

### 2D 文件支持

- 支持 **DWG** 格式（`.dwg`）
- 当 DWG 不存在时自动回退到同名 **PDF** 格式（`.pdf`）
- 多源目录递归扫描，记录文件修改时间
- 多个 DWG 匹配时，自动选择最新日期的版本

### 3D 文件支持

- 支持 **STEP** 格式（`.step`、`.stp`）
- 可选包含 **XT** 格式（`.xt`、`.x_t`）
- 多源目录递归扫描，海量文件快速索引

### 打包与输出

- 每个清单项生成独立的 ZIP 压缩包，文件名与清单名称一致
- 同时包含找到的 2D 和 3D 文件
- 支持 3D 文件按清单重命名（可选）
- 缺失文件时仍会打包（CSV 日志中明确记录找到/缺失情况）

### 配置与管理

- 图形化配置管理，无需手动编辑配置文件
- 内置清单管理功能，方便编辑待处理文件列表
- 独立的 2D 源目录与 3D 源目录管理
- 支持本地路径和局域网 UNC 路径（如 `\\192.168.160.2\生产管理部\2D\...`）

### 结果与日志

- 自动生成 CSV 日志（GBK 编码，兼容 Excel）
- 完整的处理统计报告，含成功率、速度等
- 支持任务终止功能，可随时停止打包操作

### 界面

- 顶部分别显示标题、版本信息、主题切换、GitHub链接、使用说明、更新日志、关于
- 左侧面板：文件设置、选项、执行按钮（开始打包、停止处理、配置管理、清单管理等）
- 右侧面板：处理进度条、统计信息、实时日志显示
- 底部状态栏：当前运行状态

## 快速开始

### 环境要求

- Python >= 3.9
- Windows 操作系统

### 直接运行源码

```
pip install -r requirements.txt
python .\app.py
```

## 构建

### 打包为单文件 exe

```
.\scripts\build_exe.ps1
```

构建完成后保留产物：

```
dist\obara-gunbag-fetcher.exe
```

构建脚本会自动创建临时虚拟环境、安装依赖、调用 PyInstaller，并在结束后清理 `.venv`、`build`、spec 文件、缓存等过程文件。

## 配置说明 (`config.ini`)

```
[Paths]
output_dir_name = output
original_list_file = Original file list.txt
log_file = Fetch log.csv

[Settings]
max_workers = 12
retry_attempts = 3
rename_3d_files = false
include_xt_format = false

[3D_SourceDirectories]
source_1 = \\192.168.160.2\生产管理部3d\3D 资料\设计一课3D资料\03-SV GUN STEP
source_2 = \\192.168.160.2\生产管理部3d\3D 资料\吉利标准化\07吉利库STEP
...

[2D_SourceDirectories]
source_1 = \\192.168.160.2\生产管理部\2D\已导入PDM
```

| 配置项 | 说明 | 示例 |
|---|---|---|
| `output_dir_name` | 本地输出目录名称 | `output` |
| `original_list_file` | 待处理文件清单 | `Original file list.txt` |
| `log_file` | 日志文件名 | `Fetch log.csv` |
| `max_workers` | 最大并发线程数 | `12`（建议 4~32） |
| `retry_attempts` | 打包失败重试次数 | `3` |
| `rename_3d_files` | 是否按清单重命名 3D 文件 | `true` / `false` |
| `include_xt_format` | 是否包含 XT 格式文件 | `true` / `false` |
| `3D_SourceDirectories` 的 `source_*` | 3D 源目录（完整 UNC 或本地路径） | `\\192.168.160.2\...` |
| `2D_SourceDirectories` 的 `source_*` | 2D 源目录（完整 UNC 或本地路径） | `\\192.168.160.2\...` |

## 使用步骤

1. **准备清单文件** — 创建 `.csv` 或 `.txt` 文件，每行一个文件名（无需后缀）：

```
SDEX-C0681L
SDEX-C1036L(500-340)
SDZX-C1195L
SRTX-2C14693L
```

支持自动清理后缀如 `-L`, `L(` 等。

2. **配置 `config.ini`** — 确保路径正确，特别是源目录路径；默认 2D 源目录已预置为 `\\192.168.160.2\生产管理部\2D\已导入PDM`，可按需增删。

3. **启动程序** — 双击 `obara-gunbag-fetcher.exe`，程序自动加载配置和默认清单。

4. **开始打包** — 点击"开始批量打包"，等待完成。

5. **查看结果** — 在输出目录（默认 `output`）中可看到按清单命名的 ZIP 文件，CSV 日志记录每个清单项的找到/缺失情况。

## 文件获取规则

### 2D 文件

1. 优先获取 DWG 格式文件，没有再寻找同名的 PDF 文件。
2. 所有 2D 源目录都会被扫描；当存在多个 DWG 匹配时，以**最新修改日期**为准。
3. 默认 2D 源目录：`\\192.168.160.2\生产管理部\2D\已导入PDM`，可在配置管理中增删。

### 3D 文件

- 规则与 [3d-batch-copy](https://github.com/caifugao110/3d-batch-copy) 完全一致：
  - 支持按清单重命名（可选）；
  - 可选包含 XT 格式；
  - 默认 3D 源目录与该项目保持一致。

## 日志与统计

### 日志格式（CSV，GBK 编码）

| 原始文件名 | ZIP文件名 | 找到的文件 | 缺失的文件 | 状态 |
|---|---|---|---|---|
| SRTX-2C14700L | SRTX-2C14700L.zip | 3D:SRTX-2C14700L.STEP;2D:SRTX-2C14700L.DWG | 无 | success |
| SRTX-2C14701L | SRTX-2C14701L.zip | 2D:SRTX-2C14701L.PDF | 3D | success |
| SRTX-2C14702L | 未找到任何文件 | 无 | 3D;2D | not_found |

### 处理统计报告

```
============================================================
📊 处理统计报告
============================================================
 总文件数: 100
 ✅ 成功打包: 95 (95.0%)
 ❌ 未找到: 3 (3.0%)
 ⚠️ 打包错误: 2
⏱️ 总耗时: 8.2秒 | 平均速度: 12.2 文件/秒
 3D重命名模式: 启用
 包含 XT: 是
============================================================
```

若失败率 > 50%，会弹出警告提示。

## 常见问题 (FAQ)

### 配置文件不存在？

请确保 `config.ini` 与 `exe` 文件在同一目录。

### 无法访问网络路径？

检查网络路径是否正确，或手动映射网络驱动器。

### 打包速度慢？

尝试增加 `max_workers`（如 16 或 24），但不要超过 CPU 核心数。

### 文件名匹配失败？

程序会自动清理 `-L`, `L(` 等后缀，但仍需保证基础名称一致。

### 2D 文件没找到？

- 确认 `2D_SourceDirectories` 中已配置该文件所在的网络/本地目录；
- 文件名是否需要清理后缀才能匹配；
- PDF 备用：若 DWG 找不到，会回退找同名 PDF。

## 项目结构

```
obara-gunbag-fetcher/
├── app.py                  # GUI 主程序，包含全部核心逻辑
├── assets/
│   └── app.ico             # 应用图标
├── scripts/
│   └── build_exe.ps1       # Windows 构建脚本
├── .github/
│   └── workflows/
│       └── release.yml     # GitHub Actions 自动构建发布
├── .gitignore
├── LICENSE
├── README.md
├── pyproject.toml          # 项目元数据与依赖配置
├── requirements.txt        # pip 依赖清单
├── config.ini              # 用户配置文件
└── Original file list.txt  # 待处理文件清单
```

| 条目 | 说明 |
|---|---|
| `app.py` | GUI 主程序，包含全部核心逻辑 |
| `assets/` | 图标资源 |
| `scripts/` | 构建脚本 |
| `pyproject.toml` | 项目元数据与依赖配置 |
| `requirements.txt` | pip 依赖清单 |

## License

MIT © Tobin
