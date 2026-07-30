# obara-gunbag-fetcher

*2D/3D 文件批量获取与打包工具 — 根据文件清单从多个网络或本地源目录中查找 2D（DWG/PDF）和 3D（STEP/XT）文件，并将每个清单项打包为独立的 ZIP 压缩包。*

![Python](https://img.shields.io/badge/python-3.9%2B-brightgreen)
![OS](https://img.shields.io/badge/os-windows-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## 简介

**obara-gunbag-fetcher** 是一款基于 Python 的桌面 GUI 工具，专为 OBARA 有调图需求的人员打造，用于从多个网络或本地目录中快速查找 2D 和 3D 文件，并按清单逐项打包为 ZIP 压缩包。

| 项目信息 | |
|---|---|
| 作者 | **Tobin** |
| 项目地址 | https://github.com/caifugao110/obara-gunbag-fetcher |
| 开源协议 | MIT |

## 技术栈

| 类别 | 技术 | 说明 |
|---|---|---|
| 语言 | Python 3.9+ | 主程序语言 |
| GUI 框架 | [ttkbootstrap](https://ttkbootstrap.readthedocs.io/) | 基于 tkinter 的现代化主题框架 |
| HTTP 客户端 | requests | 用于获取更新日志和在线帮助 |
| 打包工具 | PyInstaller | 构建单文件可执行程序 |
| 并发处理 | ThreadPoolExecutor + threading | 多线程索引构建与批量处理 |

## 功能特性

### 双模式运行

- **普通模式**：按清单逐项打包到输出目录，每次运行清空并重建输出目录
- **仕样号模式**（Spec Mode）：输入 5 位仕样号，按仕样号创建子目录进行追加打包
  - 支持多仕样号分批打包，已有 ZIP 文件自动跳过不重复打包
  - 仕样号目录不清空，保留历史打包记录
  - 仕样号输入框自动校验（仅允许 5 位数字）

### 2D 文件支持

- 支持 **DWG** 格式（`.dwg`）
- 当 DWG 不存在时自动回退到同名 **PDF** 格式（`.pdf`）
- 多源目录递归扫描，记录文件修改时间
- 多个 DWG 匹配时，按**路径优先级**和**修改时间**双重判定：
  - 优先选择路径中含「已导入PDM」的文件
  - 同等优先级下，选择**最新修改日期**的版本
- 三级缓存机制优化扫描性能：
  - **会话内存缓存**：同会话内重复调用直接命中
  - **磁盘缓存**（`.gunbag_cache.pkl`）：跨会话复用，源目录不变即命中
  - **全量扫描**：缓存失效时自动执行，完成后回写缓存

### 3D 文件支持

- 支持 **STEP** 格式（`.step`、`.stp`）
- 可选包含 **XT** 格式（`.xt`、`.x_t`）
- 多源目录递归扫描，海量文件快速索引
- 多线程并行扫描各源目录，充分利用多核性能

### 打包与输出

- 每个清单项生成独立的 ZIP 压缩包，文件名与清单名称一致
- 仅当 **2D 和 3D 文件都齐全** 时才会压缩为 ZIP，缺任意一个则不压缩
- 支持 3D 文件按清单重命名（可选）
- 若 2D 和 3D 均未找到，标记为 `not_found` 跳过该项
- 若仅找到其中一种（缺 2D 或缺 3D），标记为 `incomplete` 不压缩
- 自动清空并重建输出目录（普通模式）
- 仕样号模式下不清空目录，追加打包

### 配置与管理

- 图形化配置管理，无需手动编辑配置文件
- 内置清单管理功能，方便编辑待处理文件列表
- 独立的 2D 源目录与 3D 源目录管理
- 支持本地路径和局域网 UNC 路径（如 `\\192.168.160.2\生产管理部\2D\...`）
- 选项变更即时保存到配置文件
- 仕样号文件夹路径独立于普通模式输出目录配置

### 索引与缓存

- **索引重建开关**：可选择在打包前是否重建索引
- **按需重建**：关闭重建后，复用上次索引结果，加速启动
- **智能失效**：源目录变更时自动使缓存失效
- **多线程扫描**：2D 扫描采用 BFS + 多线程工作池，3D 扫描使用多线程并行
- **启动时后台索引重建**：开启 `rebuild_index_on_startup` 后，程序启动时自动在后台线程静默重建 2D/3D 索引，完成后原子覆盖缓存，不阻塞界面操作
  - 构建期间使用临时变量存储结果，全部完成后一次性写入磁盘缓存和会话缓存
  - 防止用户在建索引期间开始打包导致使用不完整的索引
  - 重建完成后状态栏会显示索引更新时间

### 后台索引重建机制

程序启动时（若 `rebuild_index_on_startup = true`），会在后台线程中依次：

1. 构建 2D 索引（静默模式，不打印进度）
2. 构建 3D 索引（静默模式）
3. 全部完成后原子写入磁盘缓存（`.gunbag_cache.pkl`）
4. 通过回调通知 UI 更新索引时间戳

整个过程不阻塞主线程，用户可以在重建期间继续操作界面（但建议等重建完成后再开始打包，以使用最新的索引）。

### 结果与日志

- 自动生成 CSV 日志（GBK 编码，兼容 Excel）
- 完整的处理统计报告，含成功率、速度、跳过数量、文件不完整数量等
- 支持任务终止功能，可随时停止打包操作

### 界面特性

- 顶部分别显示标题、模式切换（普通/仕样号）、主题切换、GitHub 链接、使用说明、更新日志、关于
- **模式切换**：顶部工具栏的分段开关，一键切换普通模式与仕样号模式
- **主题切换**：内置多种 ttkbootstrap 主题，实时切换（默认主题：`yeti`）
- 左侧面板：
  - **文件设置**：选择配置文件和原始清单文件
  - **选项**：3D 重命名开关、XT 格式包含开关、索引重建开关；第四个选项槽位根据模式动态切换（普通模式显示「优先保存在桌面」开关，仕样号模式显示 5 位数字输入框）
  - **执行**：开始批量打包、停止处理、配置管理、图号管理、打开输出目录、查看日志、清空日志框
- 右侧面板：处理进度条（含百分比）、统计信息（已处理/成功/失败/跳过/速度）、实时日志显示
- 底部状态栏：
  - 左侧：当前运行状态（初始化/配置已加载/任务运行中/任务完成等），仕样号模式下显示仕样号目录路径
  - 右侧：索引更新时间戳、本机 IP 地址、计算机主机名
- **自动加载**：启动时自动加载 `config.ini` 和默认清单文件
- **在线更新日志**：从 Gitee Commits API 实时获取最近 5 条版本记录
- **在线帮助文档**：内置使用说明窗口，从 Gitee 加载 README.md 内容
- **关于对话框**：显示项目名称、版本、作者、协议、项目链接
- **窗口关闭保护**：处理中关闭窗口会弹出确认对话框，防止误操作
- **配置管理二次确认**：修改公共配置文件时弹出"这是公共配置文件，修改需要管理员许可"二次确认
- **仕样号输入框实时校验**：只允许 5 位纯数字，非法字符自动过滤，超长自动截断

## 快速开始

### 环境要求

- Python >= 3.9
- Windows 操作系统
- 网络访问权限（如需使用 UNC 路径）

### 直接运行源码

```bash
pip install -r requirements.txt
python .\app.py
```

### 安装为命令行工具（可选）

```bash
pip install -e .
obara-gunbag-fetcher
```

## 构建

### 打包为单文件 exe

```powershell
.\scripts\build_exe.ps1
```

构建完成后产物：

```
dist\obara-gunbag-fetcher.exe
```

构建脚本会自动：
1. 创建临时虚拟环境 `.venv`
2. 升级 pip 并安装项目依赖 + PyInstaller
3. 从 `pyproject.toml` 自动生成 Windows 版本信息（产品名、版本号、公司名、版权等）
4. 调用 PyInstaller 打包为单文件窗口程序（`--onefile --windowed`），图标嵌入 exe
5. 复制 `config.ini` 和清单文件到 `dist/`
6. 清理 `dist/` 下残留的 `assets/` 文件夹
7. 清理临时文件（可通过 `-SkipCleanup` 参数跳过）

### PyInstaller 打包参数

| 参数 | 值 | 说明 |
|---|---|---|
| `--name` | `obara-gunbag-fetcher` | 输出的 exe 名称 |
| `--onefile` | — | 打包为单文件 |
| `--windowed` | — | 不显示控制台窗口 |
| `--noupx` | — | 不使用 UPX 压缩（避免杀毒软件误报） |
| `--clean` | — | 清理临时缓存 |
| `--noconfirm` | — | 不提示确认覆盖 |
| `--add-data` | `assets;assets` | 将图标等资源嵌入可执行程序 |
| `--add-data` | `pyproject.toml;.` | 嵌入项目元数据 |
| `--add-data` | `config.ini;.` | 嵌入默认配置文件 |
| `--icon` | `assets/app.ico` | 设置应用图标 |
| `--collect-data` | `ttkbootstrap` | 收集 ttkbootstrap 主题数据 |
| `--collect-all` | `requests` | 收集 requests 模块全部内容 |
| `--collect-all` | `urllib3` | 收集 urllib3 模块全部内容 |
| `--hidden-import` | `requests, urllib3, charset_normalizer, idna, certifi` | 显式声明隐式导入的子模块 |
| `--version-file` | 临时生成 | 从 pyproject.toml 动态生成的 Windows 版本信息 |

### Windows 版本信息

构建脚本会从 `pyproject.toml` 读取项目元数据，自动生成 Windows 可执行文件的版本信息资源，包含：

- 产品名称、文件描述
- 文件版本（如 `1.0.8.0`）
- 公司/作者名
- 版权声明（`Copyright (C) 2026 Tobin. All rights reserved.`）
- 原始文件名（`obara-gunbag-fetcher.exe`）
- 产品版本

这些信息在 Windows 资源管理器的"属性 → 详细信息"中可见。

### 构建选项

| 参数 | 说明 |
|---|---|
| `-ProjectDir` | 指定项目目录（默认为脚本所在目录） |
| `-SkipCleanup` | 跳过构建后的清理步骤，保留 `.venv`、`build`、spec 文件 |

### GitHub Actions 自动构建

项目已配置 GitHub Actions CI/CD（`.github/workflows/release.yml`），在 push 到 `master` 分支时自动：
1. 读取 `pyproject.toml` 中的版本号
2. 使用 `git log -1` 提取最新提交信息作为 Release 正文
3. 创建 Git 标签（格式 `V{version}`）并推送到远程
4. 在 `windows-latest` runner 上使用 Python 3.11 调用 PyInstaller 生成 exe
5. 创建 GitHub Release 并上传 `obara-gunbag-fetcher.exe` 产物

> **注意**：GitHub Actions 使用简化版 PyInstaller 参数（不含 `--noupx`、版本信息文件、`--clean`、`--noconfirm`），与本地构建脚本略有差异。本地构建脚本（`scripts/build_exe.ps1`）功能更完整。

> **注意**：运行时更新日志和帮助文档从 Gitee 获取（参见下方"服务端说明"），构建产物托管在 GitHub Releases。

## 配置说明 (`config.ini`)

```ini
[Paths]
output_dir_name = gunbag
original_list_file = Original file list.txt
log_file = Fetch log.csv

[Settings]
max_workers = 24
retry_attempts = 3
rename_3d_files = false
include_xt_format = false
rebuild_index_before_pack = false
rebuild_index_on_startup = true
log_on_desktop = true
list_on_desktop = true
prefer_desktop = true
spec_base_dir = \\SERVER\Share\临时文件\00枪衣数模

[3D_SourceDirectories]
source_1 = \\SERVER\Share\3D资料\设计一课3D资料\03-SV GUN STEP
source_2 = \\SERVER\Share\3D资料\吉利标准化\07吉利库STEP
source_3 = \\SERVER\Share\3D资料\设计一课3D资料\01-SV GUN ASSY\13-PSA\00-STP
source_4 = \\SERVER\Share\制造技术一课\checkc
...

[2D_SourceDirectories]
source_1 = \\SERVER\Share\2D\已导入PDM\二课
source_2 = \\SERVER\Share\2D\已导入PDM\上海
source_3 = \\SERVER\Share\2D\已导入PDM\一课
source_4 = \\SERVER\Share\制造技术一课\checkc
```

### 配置项说明

> **注意**：表格中的"默认值"是指当配置项缺失时代码使用的回退值，而非 `config.ini` 中的当前实际值。示例配置块展示的是本项目默认提供的 `config.ini` 内容。

| 配置项 | 类型 | 说明 | 代码回退默认值 |
|---|---|---|---|
| `output_dir_name` | string | 普通模式下的本地输出目录名称 | `output` |
| `original_list_file` | string | 待处理文件清单文件名 | `Original file list.txt` |
| `log_file` | string | 日志文件名 | `Fetch log.csv` |
| `max_workers` | int | 最大并发线程数（建议 4~32） | `12` |
| `retry_attempts` | int | 打包失败重试次数 | `3` |
| `rename_3d_files` | bool | 是否按清单重命名 3D 文件 | `false` |
| `include_xt_format` | bool | 是否包含 XT 格式文件 | `false` |
| `rebuild_index_before_pack` | bool | 打包前是否重建索引（开启时跳过缓存强制全量扫描） | `true` |
| `rebuild_index_on_startup` | bool | 启动时是否在后台静默重建索引，完成后自动覆盖缓存 | `true` |
| `log_on_desktop` | bool | 日志文件是否保存到桌面（开启时日志输出至桌面，否则保存到程序目录） | `true` |
| `list_on_desktop` | bool | 图号清单编辑保存时是否保存到桌面（开启时清单管理保存到桌面） | `true` |
| `prefer_desktop` | bool | 优先将输出保存到桌面 gunbag 目录（普通模式下生效） | `true` |
| `spec_base_dir` | string | 仕样号模式下的根目录，按仕样号创建子目录 | `\\SERVER\Share\临时文件\00枪衣数模` |
| `3D_SourceDirectories.source_*` | string | 3D 源目录（完整 UNC 或本地路径） | — |
| `2D_SourceDirectories.source_*` | string | 2D 源目录（完整 UNC 或本地路径） | — |

### 配置热更新

在 GUI 中勾选/取消以下选项时，配置会**即时保存**到 `config.ini` 并重新加载：

- **按照清单重命名 3D 文件** — 切换开关立即保存
- **包含 XT 格式 3D 文件** — 切换开关立即保存
- **重建 2D/3D 目录索引** — 切换开关立即保存，关闭时清空缓存以加速下次启动
- **优先保存在桌面 gunbag 目录** — 切换开关立即保存，开启后输出目录切换至桌面
- **启动时后台重建索引** — 在"配置管理"中修改，下次启动时生效
- **日志文件保存在桌面** — 在"配置管理"中修改，下次打包时生效
- **图号清单保存在桌面** — 在"配置管理"中修改，图号管理保存时使用

通过"配置管理"按钮保存的变更也会立即写入 `config.ini`，无需重启程序。

> **注意**：配置管理窗口会弹出二次确认提示（"这是公共配置文件，修改需要管理员许可"），防止误操作。

### 进程关闭行为

- **处理中关闭窗口**：程序会弹出确认对话框提示"当前正在处理文件，确定要退出吗？"，确认后先终止正在进行的任务，再安全退出
- **停止按钮**：点击"停止处理"后，当前正在处理的文件完成打包后会安全停止，已完成的 ZIP 文件不会丢失
- **退出保护**：关闭窗口时会自动刷新缓冲区，确保日志信息不丢失

## 使用步骤

### 普通模式

1. **准备清单文件** — 创建 `.csv` 或 `.txt` 文件，每行一个文件名（无需后缀）：

```
SDEX-C0681L
SDEX-C1036L(500-340)
SDZX-C1195L
SRTX-2C14693L
```

程序会自动清理文件名中的后缀如 `-L`、`L(` 等。

2. **启动程序** — 双击 `obara-gunbag-fetcher.exe`，程序自动加载：
   - `config.ini` 配置文件
   - `Original file list.txt` 清单文件（若存在）

3. **选择模式** — 确认顶部模式切换为"普通模式"（默认启动时为仕样号模式，需手动切换）。

4. **配置检查** — 确认源目录路径正确，可通过"配置管理"按钮进行增删改。

5. **开始打包** — 点击"开始批量打包"按钮，等待完成。

6. **查看结果** — 在输出目录（默认 `gunbag`）中可看到：
   - 按清单命名的 ZIP 文件（仅包含 2D 和 3D 都齐全的项）
   - CSV 日志文件记录每个清单项的找到/缺失/不完整情况

### 仕样号模式

1. **切换模式** — 默认启动即为「仕样号模式」，确认顶部工具栏的「仕样号模式」被选中。

2. **输入仕样号** — 在左侧面板「选项」区域的仕样号输入框中输入 5 位数字（如 `00123`）。

3. **确认仕样号目录** — 底部状态栏显示仕样号目录路径（基于 `spec_base_dir` 配置 + 仕样号）。

4. **准备清单文件** — 与普通模式相同，准备 `.csv` 或 `.txt` 文件。

5. **开始打包** — 点击"开始批量打包"按钮。程序会：
   - 自动创建仕样号子目录（如 `\\SERVER\Share\临时文件\00枪衣数模\00123\`）
   - 若目录已存在，则追加打包（已存在的 ZIP 自动跳过）
   - 不清空目录，保留历史打包记录

6. **查看结果** — 在仕样号子目录中查看 ZIP 文件。

> **提示**：可多次运行同一仕样号，已打包的文件会被跳过，仅追加新增文件。

### 输出目录结构

#### 普通模式

```
{输出目录名}/
├── SDEX-C0681L.zip           # 按清单项命名的 ZIP 压缩包
├── SDEX-C1036L.zip
├── SDZX-C1195L.zip
├── ...
└── Fetch log.csv              # 日志文件（CSV，GBK 编码）
```

#### 仕样号模式

```
{spec_base_dir}/
├── 00123/                     # 仕样号子目录
│   ├── SDEX-C0681L.zip
│   ├── SDEX-C1036L.zip
│   └── Fetch log.csv
├── 00456/                     # 另一仕样号
│   ├── SDZX-C1195L.zip
│   └── Fetch log.csv
└── ...
```

每个 ZIP 包内部结构示例：

```
SDEX-C0681L.zip
├── SDEX-C0681L.STEP          # 3D 文件（按清单重命名时使用清单名）
├── SDEX-C0681L.DWG           # 2D 文件（优先 DWG，若未找到则为 PDF）
```

若 DWG 文件未找到，ZIP 内会使用 PDF 替代：

```
SRTX-2C14701L.zip
├── SRTX-2C14701L.STEP
└── SRTX-2C14701L.PDF         # DWG 未找到时的 PDF 回退
```

> **注意**：
> - 仅当 2D 和 3D 文件都齐全时才会生成 ZIP，缺任意一个（标记为 `incomplete`）不会压缩
> - 若开启"3D 按清单重命名"，ZIP 内的 3D 文件名会使用清单项名称而非原始文件名

## 文件获取规则

### 文件名处理

程序会对清单项进行以下清理以匹配实际文件名（按代码执行顺序）：
1. 去除 `-L(` 及其后续内容，如 `SDEX-C1036-L(500-340)` → `SDEX-C1036`
2. 去除末尾 `-L` 后缀，如 `SDEX-C0681L` → `SDEX-C0681`
3. 去除末尾单独的 `L` 字符
4. 去除 `L(` 及其后续内容，如 `SDEX-C1036L(500-340)` → `SDEX-C1036`
5. 统一转为小写进行匹配

清理按顺序逐级执行，前一步的输出作为后一步的输入。

### 2D 文件

1. 优先获取 **DWG** 格式文件，没有再寻找同名的 **PDF** 文件
2. 所有 2D 源目录都会被扫描
3. 当存在多个 DWG 匹配时，按以下优先级选择：
   - **第一优先级**：路径中含「已导入PDM」的文件
   - **第二优先级**：同等优先级下按**最新修改日期**选取
4. 索引构建采用三级缓存机制，首次构建后可复用

### 3D 文件

- 支持 **STEP**（`.step`、`.stp`）和可选的 **XT**（`.xt`、`.x_t`）格式
- 支持按清单重命名（可选）
- 可选包含 XT 格式
- 支持多源目录并行扫描

### 仕样号模式追加规则

- 仕样号模式下，程序**不清空**输出目录
- 若某清单项对应的 ZIP 文件已存在，则自动跳过该项（状态为 `skipped`）
- 若文件不完整（仅找到 2D 或 3D 其中一种），不压缩且不跳过，记录为 `incomplete` 状态
- 已完成的 ZIP 不会被覆盖，保证增量打包安全

## 日志与统计

### 日志格式（CSV，GBK 编码）

| 原始文件名 | ZIP 文件名 | 3D 文件路径 | 2D 文件路径 | 缺失的文件 | 状态 |
|---|---|---|---|---|---|
| SRTX-2C14700L | SRTX-2C14700L.zip | D:\3D源\SRTX-2C14700L.STEP | D:\2D源\SRTX-2C14700L.DWG | 无 | success |
| SRTX-2C14701L | 缺少3D文件，未压缩 | 无 | D:\2D源\SRTX-2C14701L.PDF | 3D | incomplete |
| SRTX-2C14702L | 未找到任何文件 | 无 | 无 | 3D;2D | not_found |
| SDEX-C0681L | SDEX-C0681L.zip | D:\3D源\... | D:\2D源\... | 无 | skipped |

状态说明：
- `success` — 2D 和 3D 文件都齐全，成功打包
- `skipped` — 文件已存在，跳过（仅仕样号模式）
- `incomplete` — 仅找到 2D 或 3D 其中一种，未压缩
- `not_found` — 2D 和 3D 均未找到
- `error` — 打包失败
- `cancelled` — 用户终止

### 处理统计报告

**普通模式示例：**

```
============================================================
📊 处理统计报告
============================================================
 总文件数: 100
 ✅ 成功打包: 90 (90.0%)
 ❌ 未找到: 3 (3.0%)
 📋 文件不完整(缺2D或3D): 5 (5.0%)
 ⚠️ 打包错误: 2
⏱️ 总耗时: 8.2秒 | 平均速度: 12.2 文件/秒
 3D重命名模式: 启用
 包含 XT: 是
============================================================
```

**仕样号模式示例：**

```
============================================================
📊 处理统计报告
============================================================
 总文件数: 100
 ✅ 成功打包: 85 (85.0%)
 ⏭️ 跳过(已存在): 5
 ❌ 未找到: 3 (3.0%)
 📋 文件不完整(缺2D或3D): 5 (5.0%)
 ⚠️ 打包错误: 2
⏱️ 总耗时: 6.5秒 | 平均速度: 15.4 文件/秒
 3D重命名模式: 禁用
 包含 XT: 否
 仕样号模式: 启用
============================================================
```

## 常见问题 (FAQ)

### 配置文件不存在？

请确保 `config.ini` 与 `exe` 文件在同一目录。启动时若未找到配置文件，程序会提示"请选择配置文件"，需通过"配置管理"按钮创建新配置或手动选择已有的 `config.ini` 文件。

### 无法访问网络路径？

1. 检查网络路径是否正确（UNC 路径格式：`\\服务器名\共享名\路径`）
2. 确认已连接到公司局域网/VPN
3. 尝试手动映射网络驱动器（Windows 资源管理器 → 映射网络驱动器）
4. 检查网络共享权限是否已分配

### 打包速度慢？

- 尝试增加 `max_workers`（如 16 或 24），但不要超过 CPU 核心数
- 首次运行较慢是因为需要构建索引，后续运行可关闭"重建索引"开关以复用缓存
- 2D/3D 索引会自动缓存到磁盘（`.gunbag_cache.pkl`），下次启动直接加载

### 文件名匹配失败？

程序会自动清理 `-L`、`L(` 等后缀，但仍需保证基础名称一致。请检查：
- 清单中的文件名是否与实际文件名基础部分匹配
- 是否需要手动在"清单管理"中编辑清单

### 2D 文件没找到？

- 确认 `2D_SourceDirectories` 中已配置该文件所在的网络/本地目录
- 文件名是否需要清理后缀才能匹配
- PDF 备用：若 DWG 找不到，会回退找同名 PDF
- 尝试在配置管理中重新扫描源目录

### 为什么某些文件没有被压缩？

程序仅当 **2D 和 3D 文件都齐全** 时才会生成 ZIP 压缩包。如果只找到其中一种（缺 2D 或缺 3D），该项会被标记为 `incomplete` 状态，不会压缩。在日志文件的"缺失的文件"列可以查看具体缺少哪些文件。

### 多个 DWG 文件匹配时如何选择？

程序会按以下优先级自动选择：
1. **路径含「已导入PDM」** 的文件优先（表示该文件已正式导入 PDM 系统）
2. 同等优先级下，选择**最新修改日期**的文件

如需强制使用某个特定版本，可在"配置管理"中调整源目录顺序，或将该文件所在目录命名为包含「已导入PDM」的路径。

### 索引缓存如何管理？

- 索引缓存文件为程序根目录下的 `.gunbag_cache.pkl`
- 同时存储 2D 和 3D 索引，源目录变更时缓存自动失效
- 缓存含版本号校验（`_CACHE_VERSION = 2`），版本不兼容时自动全量重建
- 写入使用临时文件 + `os.replace()` 原子替换，防止半写损坏
- 如需强制重建，可在界面勾选"重建 2D/3D 索引"选项
- 可手动删除该缓存文件以强制全量扫描

### 启动时后台索引重建是什么？

程序启动时若 `rebuild_index_on_startup = true`，会在后台线程静默重建 2D/3D 索引。特点：

- **不阻塞界面**：重建过程在后台线程进行，用户可以继续操作
- **原子覆盖**：全部构建完成后一次性写入缓存，防止使用不完整索引
- **静默模式**：不打印扫描进度日志
- **状态栏提示**：完成后状态栏会显示索引更新时间
- 可在"配置管理"中关闭此功能，以加速启动（代价是索引可能不是最新的）

### "重建索引"选项和启动时后台重建有什么区别？

| 特性 | 启动时后台重建 | 打包前重建 |
|---|---|---|
| 触发时机 | 程序启动时 | 每次点击"开始批量打包"时 |
| 运行方式 | 后台线程，不阻塞界面 | 同步，打包前必须等待完成 |
| 静默模式 | 是（不打印进度） | 否（打印扫描进度） |
| 缓存策略 | 强制跳过所有缓存 | 首次打包跳过缓存，同会话后续打包复用缓存 |
| 配置项 | `rebuild_index_on_startup` | `rebuild_index_before_pack` |

### 仕样号模式使用说明

1. 切换到「仕样号模式」
2. 在输入框中输入 5 位数字仕样号（如 `00123`）
3. 准备好清单文件后点击"开始批量打包"
4. 程序会在 `spec_base_dir` 下创建以仕样号命名的子目录
5. 再次运行同一仕样号时，已存在的 ZIP 会被跳过

### 如何停止正在进行的打包任务？

点击左侧面板的"停止处理"按钮，当前正在处理的文件完成后会安全停止，已完成的 ZIP 文件不会丢失。

### 程序支持哪些主题？

基于 ttkbootstrap 框架，支持多种内置主题（如 `yeti`、`cosmo`、`flatly`、`superhero` 等），可在顶部下拉框中实时切换。

### 更新日志和帮助文档如何获取？

- **更新日志**：点击右上角"更新日志"按钮，从 Gitee Commits API 获取最近 5 条版本记录
- **使用说明**：点击"使用说明"按钮，在线加载 Gitee 上的 README.md 内容
- 若网络不可用，功能按钮仍可点击但内容加载会失败

### 仕样号模式和普通模式有什么区别？

| 特性 | 普通模式 | 仕样号模式 |
|---|---|---|
| 输出目录 | 固定目录，每次清空重建 | 按仕样号创建子目录，不清空 |
| 运行方式 | 单次全量打包 | 支持多仕样号追加打包 |
| 已有文件处理 | 无（每次重建） | 自动跳过已存在 ZIP |
| 目录组织 | 所有文件在同一目录 | 每个仕样号独立子目录 |

## 项目结构

```
obara-gunbag-fetcher/
├── app.py                  # GUI 主程序，包含全部核心逻辑（单文件约 2500 行）
├── assets/
│   └── app.ico             # 应用图标
├── scripts/
│   └── build_exe.ps1       # Windows 构建脚本（含版本信息生成）
├── .github/
│   └── workflows/
│       └── release.yml     # GitHub Actions 自动构建发布
├── .trae/
│   └── rules/
│       └── git-commit-message.md  # Git 提交信息规范
├── .gitignore
├── LICENSE
├── README.md               # 项目说明文档（同时作为应用内帮助文档）
├── pyproject.toml          # 项目元数据与依赖配置
├── requirements.txt        # pip 依赖清单
├── config.ini              # 用户配置文件
├── Original file list.txt  # 待处理文件清单
└── .gunbag_cache.pkl       # 2D/3D 索引磁盘缓存（运行时生成）
```

### 文件说明

| 文件/目录 | 说明 |
|---|---|
| `app.py` | 主程序入口，包含 GUI 界面、配置管理、文件扫描、打包处理等全部逻辑（单文件约 2500 行） |
| `assets/app.ico` | 应用程序图标 |
| `scripts/build_exe.ps1` | Windows PowerShell 构建脚本，自动创建虚拟环境、生成 Windows 版本信息、调用 PyInstaller |
| `.github/workflows/release.yml` | GitHub Actions CI/CD 配置，自动化构建和发布（Python 3.11 + windows-latest） |
| `.trae/rules/` | AI 辅助开发规则目录，含 Git 提交信息规范 |
| `pyproject.toml` | 项目元数据（名称、版本、作者、依赖等），同时供 `app.py` 读取版本信息和构建脚本生成版本资源 |
| `requirements.txt` | Python 依赖清单（`ttkbootstrap>=1.10.1`、`requests>=2.31.0`） |
| `config.ini` | 用户配置文件，包含路径、性能参数、源目录、仕样号目录等 |
| `Original file list.txt` | 默认的待处理文件清单 |
| `.gunbag_cache.pkl` | 运行时自动生成的 2D/3D 索引缓存文件（含版本号校验，不兼容时自动重建） |

## 核心模块（开发者参考）

> 本章节面向开发者，提供程序核心逻辑的快速索引。普通用户可跳过此部分。

### 索引构建

- `build_3d_index()`：多线程并行扫描 3D 源目录，构建 STEP/XT 文件索引
- `build_2d_index()`：带三级缓存的 2D 文件索引构建（会话缓存 → 磁盘缓存 → 全量扫描）
- `_scan_2d_tree_parallel()`：BFS 多线程工作池扫描 2D 目录树
- `rebuild_index_on_startup_background()`：启动时后台静默重建 2D/3D 索引，完成后原子覆盖缓存

### 缓存管理

- `_load_disk_cache()` / `_save_disk_cache()`：磁盘缓存（`.gunbag_cache.pkl`）读写，含版本校验
- `_load_2d_disk_cache()` / `_save_2d_disk_cache()`：2D 索引独立缓存读写
- `_load_3d_disk_cache()` / `_save_3d_disk_cache()`：3D 索引独立缓存读写
- 磁盘缓存使用 `os.replace()` 原子替换，防止半写损坏

### 文件匹配

- `find_3d_file()`：根据清理后的文件名查找 3D 文件
- `find_2d_file()`：根据清理后的文件名查找 2D 文件（DWG → PDF 回退），多个 DWG 时优先选路径含「已导入PDM」的，再按修改时间取最新
- `clean_filename()`：按顺序逐级清理 `-L(`、末尾 `-L`、末尾 `L`、`L(`，标准化为小写匹配键

### 打包处理

- `process_item()`：处理单个清单项，查找 2D 和 3D 文件并打包为 ZIP；仅当 2D 和 3D 都齐全时才压缩，缺任意一个返回 `incomplete` 状态；仕样号模式下已存在 ZIP 时跳过
- `ensure_output_directory()`：清空并重建输出目录（仅普通模式使用）
- 使用 `ThreadPoolExecutor` 实现并发处理

### 配置管理

- `load_configuration()`：加载 `config.ini`，支持普通模式和仕样号模式两种上下文
- `save_configuration()`：保存配置到 `config.ini`
- `apply_runtime_paths()`：根据当前模式和 `prefer_desktop` 设置计算运行时路径
- `load_project_metadata()`：从 `pyproject.toml` 读取项目元数据（含 tomllib 解析和正则回退两种方式）

### GUI 组件

- `GunbagFetcherApp`：主应用窗口，含模式切换（普通/仕样号）、主题切换、文件选择、选项控制、进度显示、日志显示
- `SettingsWindow`：配置管理窗口，单页布局含通用设置（线程数、重试次数、复选框选项）+ 普通/仕样号模式分区 + 3D/2D 源目录管理，保存时弹出二次确认
- `ListManagerWindow`：图号管理窗口，支持文本编辑、保存到桌面或原路径
- `UpdateLogWindow`：更新日志查看窗口，从 Gitee Commits API 获取最近 5 条版本记录
- `HelpWindow`：在线帮助文档窗口，从 Gitee 加载 README.md 内容
- `StdoutRedirector`：stdout 重定向器，将 print 输出重定向到 GUI 日志队列

### 仕样号模式相关

- `SPEC_BASE_DIR`：默认仕样号根目录常量
- `SPEC_PLACEHOLDER`：仕样号输入框占位提示
- `_get_spec_number()`：获取并校验当前输入的仕样号
- 仕样号模式下 `process_item()` 会检查 ZIP 是否已存在，存在则跳过
- 仕样号模式启动时校验 5 位纯数字，不合法则阻止打包
- 仕样号模式下输出目录不清空，追加打包

### 全局缓存与状态变量

- `_2D_INDEX_CACHE`：会话级 2D 索引缓存（`cache_key → (index, dwg_count, pdf_count, scan_dirs)`）
- `_3D_INDEX_CACHE`：会话级 3D 索引缓存（`cache_key → index`）
- `_INDEX_REBUILT_THIS_SESSION`：标记本会话是否已重建索引，用于跳过重复重建
- `_STARTUP_INDEX_REBUILDING`：标记启动时后台重建是否正在进行
- `_STARTUP_INDEX_REBUILT`：标记启动时后台重建是否已完成
- `log_queue` / `progress_queue`：日志队列和进度队列，用于后台线程与 GUI 线程通信

## 服务端说明

本项目运行时依赖以下外部服务：

| 服务 | 用途 | 地址 |
|---|---|---|
| Gitee Commits API | 获取最近 5 条版本更新日志 | `https://gitee.com/api/v5/repos/caifugao110/obara-gunbag-fetcher/commits` |
| Gitee 原始文件 | 加载在线使用说明（README.md） | `https://gitee.com/caifugao110/obara-gunbag-fetcher/raw/master/README.md` |
| GitHub | 项目主页、源码托管、Release 构建产物 | `https://github.com/caifugao110/obara-gunbag-fetcher` |

> **注意**：若 Gitee 服务不可用，更新日志和使用说明功能将无法使用，但不影响核心打包功能。

## License

MIT © Tobin
