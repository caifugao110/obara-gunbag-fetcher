from __future__ import annotations

import configparser
import csv
import os
import pickle
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk

import requests
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, X, YES


def configure_standard_streams() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


configure_standard_streams()


def bundled_path(name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name
    return Path(__file__).resolve().parent / name


def load_project_metadata() -> dict[str, str]:
    pyproject_path = bundled_path("pyproject.toml")
    metadata = {
        "name": "obara-gunbag-fetcher",
        "version": "1.0.0",
        "author": "Tobin",
        "homepage": "https://github.com/caifugao110/obara-gunbag-fetcher",
    }
    if not pyproject_path.exists():
        return metadata

    text = pyproject_path.read_text(encoding="utf-8")
    try:
        import tomllib

        project = tomllib.loads(text).get("project", {})
        urls = project.get("urls", {})
        authors = project.get("authors", [])
        metadata["name"] = project.get("name", metadata["name"])
        metadata["version"] = project.get("version", metadata["version"])
        if authors:
            metadata["author"] = authors[0].get("name", metadata["author"])
        metadata["homepage"] = urls.get("Homepage", metadata["homepage"])
        return metadata
    except Exception:
        pass

    patterns = {
        "name": r'(?m)^name\s*=\s*"([^"]+)"',
        "version": r'(?m)^version\s*=\s*"([^"]+)"',
        "author": r'authors\s*=\s*\[\{\s*name\s*=\s*"([^"]+)"',
        "homepage": r'(?m)^Homepage\s*=\s*"([^"]+)"',
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            metadata[key] = match.group(1)
    return metadata


PROJECT_METADATA = load_project_metadata()
PROJECT_NAME = PROJECT_METADATA["name"]
__version__ = PROJECT_METADATA["version"]
__author__ = PROJECT_METADATA["author"]
__homepage__ = PROJECT_METADATA["homepage"]

VERSION = f"V{__version__}"
COPYRIGHT = f"{__author__} © 2026"
PROJECT_URL = __homepage__

log_queue: queue.Queue[str] = queue.Queue()
progress_queue: queue.Queue[tuple] = queue.Queue()


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_root_path() -> str:
    """获取程序根目录（exe所在目录，支持PyInstaller打包后路径）。"""
    return str(project_root())


def asset_path(name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / name
    return project_root() / "assets" / name


ASSET_ICON = asset_path("app.ico")


def open_path(path: str | Path) -> None:
    target = str(path)
    if sys.platform.startswith("win"):
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


def center_window(window: tk.Toplevel, parent: tk.Misc, width: int, height: int) -> None:
    parent.update_idletasks()
    x = parent.winfo_rootx() + max((parent.winfo_width() - width) // 2, 0)
    y = parent.winfo_rooty() + max((parent.winfo_height() - height) // 2, 0)
    window.geometry(f"{width}x{height}+{x}+{y}")


def get_update_logs(count=5):
    """从Gitee Releases API获取最近count条更新记录。"""
    api_url = "https://gitee.com/api/v5/repos/caifugao110/obara-gunbag-fetcher/releases"
    headers = {
        "Authorization": "token a09da64c1d9e9c7420a18dfd838890b0",
    }
    try:
        response = requests.get(api_url, headers=headers, timeout=5)
        response.raise_for_status()
        releases = response.json()

        version_pattern = re.compile(r"v?(\d+\.\d+\.\d+)", re.IGNORECASE)
        updates = []

        for release in releases:
            tag_name = release.get("tag_name", "")
            match = version_pattern.search(tag_name)
            if match:
                version_str = match.group(1)
                version_tuple = tuple(map(int, version_str.split(".")))
                changelog = "暂无更新说明"
                try:
                    commit_url = f"https://gitee.com/api/v5/repos/caifugao110/obara-gunbag-fetcher/commits/{tag_name}"
                    commit_resp = requests.get(commit_url, headers=headers, timeout=5)
                    commit_resp.raise_for_status()
                    commit_data = commit_resp.json()
                    changelog = commit_data.get("commit", {}).get("message", "").strip() or "暂无更新说明"
                except Exception:
                    body = release.get("body", "")
                    match_info = re.search(r"最后提交信息为.*?[:：]\s*(.*)", body, re.DOTALL)
                    if match_info:
                        extracted = match_info.group(1).strip()
                        if extracted:
                            changelog = extracted
                created_at = release.get("created_at", "")[:10] if release.get("created_at") else ""
                updates.append(
                    {
                        "version": tag_name,
                        "version_tuple": version_tuple,
                        "changelog": changelog,
                        "date": created_at,
                    }
                )

        updates.sort(key=lambda x: x["version_tuple"], reverse=True)
        return [{k: v for k, v in item.items() if k != "version_tuple"} for item in updates[:count]]

    except Exception as e:
        print(f"⚠️ 获取更新日志失败: {str(e)}")
        return []


def clean_filename(name):
    """清理文件名: 去除特定后缀和标识符，统一转为小写。"""
    if "-L(" in name:
        parts = name.split("-L(")
        name = parts[0]
    if name.endswith("-L"):
        parts = name.split("-L")
        name = parts[0]
    if name.endswith("L"):
        name = name[:-1]
    if "L(" in name:
        parts = name.split("L(")
        name = parts[0]
    return name.lower()


def load_configuration(config_path):
    """加载配置文件。"""
    if not os.path.exists(config_path):
        print(f"🔥 配置文件不存在: {config_path}")
        print("⚠️ 请确保 config.ini 文件与exe在同一目录下")
        return None

    try:
        config = configparser.ConfigParser()
        config.optionxform = lambda option: option
        config.read(config_path, encoding="utf-8")

        output_dir_name = config.get("Paths", "output_dir_name")
        original_list_filename = config.get("Paths", "original_list_file")
        log_filename = config.get("Paths", "log_file")
        rename_option = config.getboolean("Settings", "rename_3d_files", fallback=False)
        include_xt = config.getboolean("Settings", "include_xt_format", fallback=False)
        rebuild_index = config.getboolean("Settings", "rebuild_index_before_pack", fallback=True)

        root_path = get_root_path()
        source_dirs_3d = []
        if "3D_SourceDirectories" in config:
            for key in config["3D_SourceDirectories"]:
                full_path = config.get("3D_SourceDirectories", key)
                source_dirs_3d.append(full_path)

        source_dirs_2d = []
        if "2D_SourceDirectories" in config:
            for key in config["2D_SourceDirectories"]:
                full_path = config.get("2D_SourceDirectories", key)
                source_dirs_2d.append(full_path)

        output_dir = os.path.join(root_path, output_dir_name)
        list_file = os.path.join(root_path, original_list_filename)
        log_file = os.path.join(root_path, log_filename)

        max_workers = config.getint("Settings", "max_workers", fallback=12)
        retry_attempts = config.getint("Settings", "retry_attempts", fallback=3)

        print("✅ 配置加载成功:")
        print(f"   3D源目录数量: {len(source_dirs_3d)}")
        print(f"   2D源目录数量: {len(source_dirs_2d)}")
        print(f"   输出目录: {output_dir}")
        print(f"   待处理列表: {list_file}")
        print(f"   日志文件: {log_file}")
        print(f"   最大线程数: {max_workers}")
        print(f"   重试次数: {retry_attempts}")
        print(f"   3D按清单重命名: {'是' if rename_option else '否'}")
        print(f"   包含 XT 格式: {'是' if include_xt else '否'}")
        print(f"   打包前重建索引: {'是' if rebuild_index else '否'}")

        return {
            "source_dirs_3d": source_dirs_3d,
            "source_dirs_2d": source_dirs_2d,
            "output_dir": output_dir,
            "list_file": list_file,
            "log_file": log_file,
            "max_workers": max_workers,
            "retry_attempts": retry_attempts,
            "original_list_filename": original_list_filename,
            "output_dir_name": output_dir_name,
            "log_filename": log_filename,
            "config_path": config_path,
            "rename_3d_files": rename_option,
            "include_xt_format": include_xt,
            "rebuild_index_before_pack": rebuild_index,
        }
    except Exception as e:
        print(f"🔥 配置文件解析失败: {str(e)}")
        print("⚠️ 请检查 config.ini 文件格式是否正确")
        return None


def save_configuration(config_path, config_data):
    """保存配置文件。"""
    try:
        config = configparser.ConfigParser()
        config.optionxform = lambda option: option

        config["Paths"] = {
            "output_dir_name": config_data.get("output_dir_name", "output"),
            "original_list_file": config_data.get("original_list_filename", "Original file list.txt"),
            "log_file": config_data.get("log_filename", "log.csv"),
        }

        config["Settings"] = {
            "max_workers": str(config_data.get("max_workers", 12)),
            "retry_attempts": str(config_data.get("retry_attempts", 3)),
            "rename_3d_files": str(config_data.get("rename_3d_files", False)).lower(),
            "include_xt_format": str(config_data.get("include_xt_format", False)).lower(),
            "rebuild_index_before_pack": str(config_data.get("rebuild_index_before_pack", True)).lower(),
        }

        config["3D_SourceDirectories"] = {}
        for idx, src_dir in enumerate(config_data.get("source_dirs_3d", []), 1):
            config["3D_SourceDirectories"][f"source_{idx}"] = src_dir

        config["2D_SourceDirectories"] = {}
        for idx, src_dir in enumerate(config_data.get("source_dirs_2d", []), 1):
            config["2D_SourceDirectories"][f"source_{idx}"] = src_dir

        with open(config_path, "w", encoding="utf-8") as f:
            config.write(f)

        print(f"✅ 配置已保存至: {config_path}")
        return True
    except Exception as e:
        print(f"🔥 配置保存失败: {str(e)}")
        return False


def apply_runtime_paths(config_data):
    """根据当前程序根目录补齐运行时使用的文件路径。"""
    root_path = get_root_path()
    config_data["output_dir"] = os.path.join(root_path, config_data.get("output_dir_name", "output"))
    config_data["list_file"] = os.path.join(root_path, config_data.get("original_list_filename", "Original file list.txt"))
    config_data["log_file"] = os.path.join(root_path, config_data.get("log_filename", "log.csv"))
    return config_data


def ensure_output_directory(output_dir):
    """确保输出目录存在，并清空其内容。"""
    if os.path.exists(output_dir):
        print(f"📁 清空输出目录: {output_dir}")
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 输出目录已就绪: {output_dir}")


def is_xt_variant(filename):
    """判断文件名是否属于XT变体（大小写不敏感）。"""
    lower = filename.lower()
    return lower.endswith(".xt") or lower.endswith(".x_t")


def is_step_variant(filename):
    """判断是否为STEP类（.step 或 .stp 不区分大小写）。"""
    lower = filename.lower()
    return lower.endswith(".step") or lower.endswith(".stp")


def is_dwg_variant(filename):
    """判断是否为DWG类（.dwg 不区分大小写）。"""
    return filename.lower().endswith(".dwg")


def is_pdf_variant(filename):
    """判断是否为PDF类（.pdf 不区分大小写）。"""
    return filename.lower().endswith(".pdf")


def _scan_3d_dir_fast(src_dir, include_xt=False):
    """快速扫描单个3D目录（使用 os.scandir 递归），返回文件列表。"""
    results = []
    try:
        stack = [src_dir]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            name = entry.name
                            lower = name.lower()
                            is_step = lower.endswith('.step') or lower.endswith('.stp')
                            is_xt = include_xt and (lower.endswith('.xt') or lower.endswith('.x_t'))
                            if is_step or is_xt:
                                results.append((name, current))
            except (PermissionError, OSError):
                pass
    except Exception as e:
        pass
    return results


def build_3d_index(source_dirs, include_xt=False, max_workers=12, force_refresh=False):
    """构建3D文件索引（支持递归），支持可选包含 XT 格式以及 .stp。使用多线程加速。
    三级回退：会话内存缓存 → 磁盘缓存（跨会话）→ 全量扫描。
    force_refresh=True 时跳过两级缓存，重新全量扫描并回写缓存。
    """
    cache_key = (tuple(sorted(source_dirs)), include_xt)

    # 1. 会话内存缓存
    if not force_refresh and cache_key in _3D_INDEX_CACHE:
        index = _3D_INDEX_CACHE[cache_key]
        print(f"✅ 3D索引命中会话缓存: {len(index)} 个前缀组（本会话已扫描过）")
        return index

    # 2. 磁盘缓存（跨会话，源目录不变即命中）
    if not force_refresh:
        disk_index = _load_3d_disk_cache(cache_key)
        if disk_index is not None:
            _3D_INDEX_CACHE[cache_key] = disk_index
            print(f"✅ 3D索引命中磁盘缓存: {len(disk_index)} 个前缀组")
            return disk_index

    # 3. 全量扫描
    print("⏳ 正在构建3D文件索引（多线程扫描）...")
    start_time = time.time()

    # 多线程并行扫描各个源目录
    all_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_scan_3d_dir_fast, src, include_xt): src for src in source_dirs}
        for future in as_completed(futures):
            src = futures[future]
            try:
                results = future.result()
                all_results.extend(results)
                if results:
                    print(f"   📁 {src}: 扫描到 {len(results)} 个文件")
            except Exception as e:
                print(f"⚠️ 目录扫描失败: {src} - {str(e)}")

    # 处理扫描结果
    index = {}
    for name, root in all_results:
        base_name = os.path.splitext(name)[0]
        clean_base = clean_filename(base_name)
        prefix_key = clean_base[:4] if len(clean_base) >= 4 else clean_base
        if prefix_key not in index:
            index[prefix_key] = []
        index[prefix_key].append((clean_base, name, root))

    total_files = len(all_results)
    index_time = time.time() - start_time
    print(f"✅ 3D索引构建完成: {len(index)} 个前缀组, {total_files} 个文件, 耗时 {index_time:.2f}秒")

    _3D_INDEX_CACHE[cache_key] = index
    _save_3d_disk_cache(cache_key, index)
    return index


# 会话级 2D 索引缓存：cache_key=(排序后的源目录元组) -> (index, dwg_count, pdf_count, scan_dirs)。
# 同会话内对相同源目录集合的重复调用直接命中，避免重复遍历网络驱动器；源目录变更则自动失效。
_2D_INDEX_CACHE: dict[tuple, tuple] = {}

# 会话级 3D 索引缓存：cache_key=(排序后的源目录元组, include_xt) -> index。
_3D_INDEX_CACHE: dict[tuple, dict] = {}

_INDEX_REBUILT_THIS_SESSION = False


def _scan_2d_dir_one(current):
    """非递归扫描单个目录（仅一层），返回 (files, subdirs)。
    files: [(ftype, name, current, mtime), ...]，ftype ∈ {'dwg','pdf'}；
    DWG 记录修改时间用于多版本择新，PDF 仅作回退故存 0。
    """
    files = []
    subdirs = []
    try:
        with os.scandir(current) as entries:
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        subdirs.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        name = entry.name
                        lower = name.lower()
                        if lower.endswith('.dwg'):
                            files.append(('dwg', name, current, entry.stat().st_mtime))
                        elif lower.endswith('.pdf'):
                            files.append(('pdf', name, current, 0))
                except OSError:
                    continue
    except (PermissionError, OSError):
        pass
    except Exception:
        pass
    return files, subdirs


def _scan_2d_worker_loop(dir_queue, fragments, state, cv):
    """2D 扫描工作线程：从共享目录队列取目录、扫描一层、子目录回填队列，
    把文件就地写入线程本地 index 片段。队列空且无活跃扫描时退出。
    """
    local_index = {}
    while True:
        # 1. 取一个目录（与终止判断原子化，都在 cv 锁内）
        with cv:
            while True:
                try:
                    current = dir_queue.get_nowait()
                    break
                except queue.Empty:
                    if state["active"] == 0:
                        # 队列空且无活跃扫描 → 全局完成，唤醒同伴一起退出
                        cv.notify_all()
                        fragments.append(local_index)
                        return
                    # 其他线程可能正在扫描并产出子目录，短暂等待
                    cv.wait(timeout=0.05)
            state["active"] += 1

        # 2. 扫描一层（不持锁，允许多线程并发 I/O）
        files, subdirs = _scan_2d_dir_one(current)

        # 3. 文件写入线程本地片段（clean_filename/splitext/prefix_key 并行化）
        for ftype, name, dirpath, mtime in files:
            base_name = os.path.splitext(name)[0]
            clean_base = clean_filename(base_name)
            prefix_key = clean_base[:4] if len(clean_base) >= 4 else clean_base
            bucket = local_index.get(prefix_key)
            if bucket is None:
                bucket = {"dwg": [], "pdf": []}
                local_index[prefix_key] = bucket
            if ftype == 'dwg':
                bucket["dwg"].append((clean_base, name, dirpath, mtime))
            else:
                bucket["pdf"].append((clean_base, name, dirpath))

        # 4. 子目录回填队列 + 状态更新（持锁）
        with cv:
            for d in subdirs:
                dir_queue.put(d)
            state["active"] -= 1
            state["scanned_dirs"] += 1
            state["scanned_files"] += len(files)
            cv.notify_all()


def _scan_2d_tree_parallel(source_dirs, max_workers):
    """并行 BFS 扫描所有源目录树（子目录级并行，自动负载均衡）。
    返回 (index, scanned_dirs, dwg_count, pdf_count)。
    """
    dir_queue = queue.Queue()
    for src in source_dirs:
        dir_queue.put(src)

    fragments = []
    state = {"active": 0, "scanned_dirs": 0, "scanned_files": 0}
    cv = threading.Condition()

    n_workers = max(1, min(max_workers, 64))
    threads = [
        threading.Thread(target=_scan_2d_worker_loop, args=(dir_queue, fragments, state, cv), daemon=True)
        for _ in range(n_workers)
    ]
    for t in threads:
        t.start()

    # 主线程等待 + 每秒进度回显
    start_time = time.time()
    last_report = 0.0
    while any(t.is_alive() for t in threads):
        time.sleep(0.2)
        now = time.time()
        if now - last_report >= 1.0:
            last_report = now
            with cv:
                d = state["scanned_dirs"]
                f = state["scanned_files"]
            print(f"   ⏱️ 已扫描 {d} 个目录, {f} 个文件, 用时 {now - start_time:.1f}s")

    for t in threads:
        t.join()

    # 合并各线程本地片段为最终 index
    index = {}
    dwg_count = 0
    pdf_count = 0
    for frag in fragments:
        for prefix_key, bucket in frag.items():
            target = index.get(prefix_key)
            if target is None:
                index[prefix_key] = bucket
            else:
                target["dwg"].extend(bucket["dwg"])
                target["pdf"].extend(bucket["pdf"])
            dwg_count += len(bucket["dwg"])
            pdf_count += len(bucket["pdf"])

    return index, state["scanned_dirs"], dwg_count, pdf_count


_CACHE_FILENAME = ".gunbag_cache.pkl"
_CACHE_VERSION = 2


def _cache_path():
    """磁盘缓存文件路径（位于程序根目录）。"""
    return os.path.join(get_root_path(), _CACHE_FILENAME)


def _load_disk_cache():
    """从磁盘加载完整缓存（含2D和3D索引）。返回 dict 或 None。"""
    path = _cache_path()
    try:
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            data = pickle.load(f)
        if not isinstance(data, dict):
            return None
        if data.get("version") != _CACHE_VERSION:
            return None
        return data
    except Exception as e:
        print(f"⚠️ 磁盘缓存读取失败，将全量扫描: {e}")
        return None


def _save_disk_cache(data):
    """把完整缓存原子写入磁盘（先写临时文件再 os.replace，避免半写损坏）。"""
    path = _cache_path()
    try:
        data["version"] = _CACHE_VERSION
        data["saved_at"] = time.time()
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)
    except Exception as e:
        print(f"⚠️ 磁盘缓存写入失败: {e}")


def _load_2d_disk_cache(cache_key):
    """从磁盘加载2D索引缓存。命中返回 (index, dwg_count, pdf_count, scan_dirs)，否则 None。"""
    disk = _load_disk_cache()
    if disk is None:
        return None
    cache_entry = disk.get("2d", {})
    if cache_entry.get("cache_key") != cache_key:
        return None
    index = cache_entry.get("index")
    if not isinstance(index, dict):
        return None
    return (index, cache_entry.get("dwg_count", 0), cache_entry.get("pdf_count", 0), cache_entry.get("scan_dirs", 0))


def _save_2d_disk_cache(cache_key, index, dwg_count, pdf_count, scan_dirs):
    """把2D索引写入磁盘缓存（与3D缓存共享同一文件）。"""
    disk = _load_disk_cache() or {}
    disk["2d"] = {
        "cache_key": cache_key,
        "index": index,
        "dwg_count": dwg_count,
        "pdf_count": pdf_count,
        "scan_dirs": scan_dirs,
    }
    _save_disk_cache(disk)


def _load_3d_disk_cache(cache_key):
    """从磁盘加载3D索引缓存。命中返回 index，否则 None。"""
    disk = _load_disk_cache()
    if disk is None:
        return None
    cache_entry = disk.get("3d", {})
    if cache_entry.get("cache_key") != cache_key:
        return None
    index = cache_entry.get("index")
    if not isinstance(index, dict):
        return None
    return index


def _save_3d_disk_cache(cache_key, index):
    """把3D索引写入磁盘缓存（与2D缓存共享同一文件）。"""
    disk = _load_disk_cache() or {}
    disk["3d"] = {
        "cache_key": cache_key,
        "index": index,
    }
    _save_disk_cache(disk)


def build_2d_index(source_dirs, max_workers=12, force_refresh=False):
    """构建2D文件索引（子目录级并行扫描），索引 DWG 和 PDF，记录修改时间。
    三级回退：会话内存缓存 → 磁盘缓存（跨会话）→ 全量扫描。
    force_refresh=True 时跳过两级缓存，重新全量扫描并回写缓存。
    """
    print("⏳ 正在构建2D文件索引（多线程扫描）...")
    start_time = time.time()

    cache_key = tuple(sorted(source_dirs))

    # 1. 会话内存缓存
    if not force_refresh and cache_key in _2D_INDEX_CACHE:
        index, dwg_count, pdf_count, scan_dirs = _2D_INDEX_CACHE[cache_key]
        total = dwg_count + pdf_count
        print(f"✅ 2D索引命中会话缓存: {len(index)} 个前缀组, {dwg_count} DWG + {pdf_count} PDF = {total} 个文件, {scan_dirs} 个目录（本会话已扫描过）")
        return index

    # 2. 磁盘缓存（跨会话，源目录不变即命中）
    if not force_refresh:
        disk = _load_2d_disk_cache(cache_key)
        if disk is not None:
            index, dwg_count, pdf_count, scan_dirs = disk
            _2D_INDEX_CACHE[cache_key] = disk
            total = dwg_count + pdf_count
            load_time = time.time() - start_time
            print(f"✅ 2D索引命中磁盘缓存: {len(index)} 个前缀组, {dwg_count} DWG + {pdf_count} PDF = {total} 个文件, {scan_dirs} 个目录, 加载 {load_time:.2f}秒")
            return index

    # 3. 全量扫描
    index, scan_dirs, dwg_count, pdf_count = _scan_2d_tree_parallel(source_dirs, max_workers)

    total_files = dwg_count + pdf_count
    index_time = time.time() - start_time
    print(f"✅ 2D索引构建完成: {len(index)} 个前缀组, {dwg_count} DWG + {pdf_count} PDF = {total_files} 个文件, 扫描 {scan_dirs} 个目录, 耗时 {index_time:.2f}秒")

    cached = (index, dwg_count, pdf_count, scan_dirs)
    _2D_INDEX_CACHE[cache_key] = cached
    _save_2d_disk_cache(cache_key, index, dwg_count, pdf_count, scan_dirs)
    return index


def read_original_file_list(list_file):
    """读取待处理文件列表（支持CSV和TXT格式）。"""
    try:
        _, ext = os.path.splitext(list_file)
        ext = ext.lower()

        if ext == ".csv":
            with open(list_file, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                all_lines = [row[0].strip() for row in reader if row and row[0].strip()]
        elif ext == ".txt":
            with open(list_file, "r", encoding="utf-8-sig") as f:
                all_lines = [line.strip() for line in f if line.strip()]
        else:
            print(f"⚠️ 不支持的文件格式: {ext}, 仅支持CSV和TXT文件")
            return None

        print(f"📋 待处理文件数: {len(all_lines)}")
        return all_lines
    except Exception as e:
        print(f"🔥 文件读取失败: {str(e)}")
        print(f"⚠️ 请检查文件是否存在且格式正确: {list_file}")
        return None


def find_3d_file(search_name, index_3d, rename_3d=False):
    """查找3D文件，返回 (src_path, src_filename, dst_name) 或 None。"""
    prefix_key = search_name[:4] if len(search_name) >= 4 else search_name
    if prefix_key not in index_3d:
        return None

    for clean_base, src_filename, src_dir in index_3d[prefix_key]:
        if clean_base == search_name:
            src_path = os.path.join(src_dir, src_filename)
            if rename_3d:
                src_ext = os.path.splitext(src_filename)[1]
                dst_name = f"{search_name}{src_ext.upper()}"
            else:
                dst_name = src_filename
            return (src_path, src_filename, dst_name)
    return None


def find_2d_file(search_name, index_2d):
    """查找2D文件，优先DWG，多个时优先选路径含"已导入PDM"的，再按修改时间取最新；没有则PDF。返回 (src_path, dst_name) 或 None。"""
    prefix_key = search_name[:4] if len(search_name) >= 4 else search_name
    if prefix_key not in index_2d:
        return None

    dwg_list = index_2d[prefix_key]["dwg"]
    pdf_list = index_2d[prefix_key]["pdf"]

    matched_dwgs = [item for item in dwg_list if item[0] == search_name]
    if matched_dwgs:
        # 优先选路径含"已导入PDM"的，再按修改时间降序取最新
        matched_dwgs.sort(key=lambda x: (0 if "已导入PDM" in x[2] else 1, -x[3]))
        _, src_filename, src_dir, _ = matched_dwgs[0]
        src_path = os.path.join(src_dir, src_filename)
        return (src_path, src_filename)

    matched_pdfs = [item for item in pdf_list if item[0] == search_name]
    if matched_pdfs:
        _, src_filename, src_dir = matched_pdfs[0]
        src_path = os.path.join(src_dir, src_filename)
        return (src_path, src_filename)

    return None


def process_item(item, output_dir, index_3d, index_2d, retry_attempts, stop_event, rename_3d, include_xt):
    """处理单个清单项：查找2D和3D文件，打包为ZIP。"""
    original_name, search_name = item

    if stop_event.is_set():
        return {
            "status": "cancelled",
            "original": original_name,
            "zip_file": "操作已取消",
            "found_3d_path": "",
            "found_2d_path": "",
            "files_missing": [],
        }

    found_3d = find_3d_file(search_name, index_3d, rename_3d=rename_3d)
    found_2d = find_2d_file(search_name, index_2d)

    files_to_pack = []
    files_missing = []
    found_3d_path = ""
    found_2d_path = ""

    if found_3d:
        src_path, src_name, dst_name = found_3d
        files_to_pack.append((src_path, dst_name))
        found_3d_path = src_path
    else:
        files_missing.append("3D")

    if found_2d:
        src_path, dst_name = found_2d
        files_to_pack.append((src_path, dst_name))
        found_2d_path = src_path
    else:
        files_missing.append("2D")

    if not files_to_pack:
        return {
            "status": "not_found",
            "original": original_name,
            "zip_file": "未找到任何文件",
            "found_3d_path": "",
            "found_2d_path": "",
            "files_missing": ["3D", "2D"],
        }

    zip_filename = f"{original_name}.zip"
    zip_path = os.path.join(output_dir, zip_filename)

    for attempt in range(retry_attempts):
        if stop_event.is_set():
            return {
                "status": "cancelled",
                "original": original_name,
                "zip_file": "操作已取消",
                "found_3d_path": found_3d_path,
                "found_2d_path": found_2d_path,
                "files_missing": files_missing,
            }

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for src_path, arcname in files_to_pack:
                    zf.write(src_path, arcname)

            return {
                "status": "success",
                "original": original_name,
                "zip_file": zip_filename,
                "found_3d_path": found_3d_path,
                "found_2d_path": found_2d_path,
                "files_missing": files_missing,
            }
        except Exception as e:
            if attempt < retry_attempts - 1:
                time.sleep(2 ** attempt)
            else:
                return {
                    "status": "error",
                    "original": original_name,
                    "zip_file": f"打包失败: {str(e)}",
                    "found_3d_path": found_3d_path,
                    "found_2d_path": found_2d_path,
                    "files_missing": files_missing,
                }

    return {
        "status": "error",
        "original": original_name,
        "zip_file": "未知错误",
        "found_3d_path": found_3d_path,
        "found_2d_path": found_2d_path,
        "files_missing": files_missing,
    }


def worker(config, progress_callback, stop_event):
    """后台工作线程：执行完整的打包流程。"""
    program_start_time = time.time()
    result_log = []
    success_count = 0
    not_found_count = 0
    pack_errors = 0

    if not config:
        progress_queue.put(("complete", False))
        return

    source_dirs_3d = config["source_dirs_3d"]
    source_dirs_2d = config["source_dirs_2d"]
    output_dir = config["output_dir"]
    list_file = config["list_file"]
    log_file = config["log_file"]
    max_workers = config["max_workers"]
    retry_attempts = config["retry_attempts"]
    rename_3d = config.get("rename_3d_files", False)
    include_xt = config.get("include_xt_format", False)

    ensure_output_directory(output_dir)

    global _INDEX_REBUILT_THIS_SESSION
    rebuild_index = config.get("rebuild_index_before_pack", True)
    force_rebuild = rebuild_index and not _INDEX_REBUILT_THIS_SESSION
    if force_rebuild:
        print("🔄 首次打包且开启重建索引：强制重建2D/3D索引（跳过缓存）")
        _2D_INDEX_CACHE.clear()
        _3D_INDEX_CACHE.clear()
        _INDEX_REBUILT_THIS_SESSION = True
    elif rebuild_index:
        print("📌 重建索引开关已开启，但本会话已重建过索引，本次跳过")

    index_3d = build_3d_index(source_dirs_3d, include_xt=include_xt, max_workers=max_workers, force_refresh=force_rebuild)
    index_2d = build_2d_index(source_dirs_2d, max_workers=max_workers, force_refresh=force_rebuild)

    original_files = read_original_file_list(list_file)
    if not original_files or len(original_files) == 0:
        print("🔥 无待处理文件，程序退出")
        progress_queue.put(("complete", False))
        return
    total_files = len(original_files)
    progress_queue.put(("max", total_files))

    search_items = [(orig, clean_filename(orig)) for orig in original_files]

    print(f"📦 开始并行打包... {'(3D将按清单重命名)' if rename_3d else ''} {'(包含XT)' if include_xt else ''}")
    executor = ThreadPoolExecutor(max_workers=max_workers)
    futures = [
        executor.submit(process_item, item, output_dir, index_3d, index_2d, retry_attempts, stop_event, rename_3d, include_xt)
        for item in search_items
    ]

    try:
        for idx, future in enumerate(as_completed(futures)):
            if stop_event.is_set():
                executor.shutdown(wait=False)
                print("⏹️ 正在终止所有打包任务...")
                break

            result = future.result()
            result_log.append(result)

            if result["status"] == "success":
                success_count += 1
            elif result["status"] == "not_found":
                not_found_count += 1
            elif result["status"] == "error":
                pack_errors += 1

            progress_queue.put(
                (
                    "update",
                    idx + 1,
                    success_count,
                    not_found_count + pack_errors,
                    (idx + 1) / max(1, time.time() - program_start_time),
                )
            )
    finally:
        executor.shutdown(wait=False)

    if not stop_event.is_set():
        write_result_log(log_file, result_log)

        total_time = time.time() - program_start_time
        print("\n" + "=" * 60)
        print("📊 处理统计报告")
        print("=" * 60)
        print(f"📊   总文件数: {total_files}")
        print(f"✅   成功打包: {success_count} ({success_count / max(1, total_files):.1%})")
        print(f"❌   未找到: {not_found_count} ({not_found_count / max(1, total_files):.1%})")
        print(f"⚠️   打包错误: {pack_errors}")
        print(f"⏱️   总耗时: {total_time:.1f}秒 | 平均速度: {total_files / max(1, total_time):.1f} 文件/秒")
        print(f"🔧   3D重命名模式: {'启用' if rename_3d else '禁用'}")
        print(f"🔧   包含 XT: {'是' if include_xt else '否'}")
        print("=" * 60)

        failure_rate = (not_found_count + pack_errors) / max(1, total_files)
        if failure_rate > 0.5:
            print(f"\n⚠️ 警告: 超过50%的文件处理失败 ({failure_rate:.1%})！")
            print("⚠️ 可能的原因:")
            print("⚠️   - 网络驱动器连接异常")
            print("⚠️   - 源目录路径不正确")
            print("⚠️   - 文件名不匹配")
            print("⚠️ 请检查配置文件和网络连接状态")

        print("\n🎉 程序执行完成！")
    else:
        print("\n⏹️ 任务已被用户终止")

    progress_queue.put(("complete", not stop_event.is_set()))


def write_result_log(log_file, result_log):
    """写入日志文件，使用GBK编码兼容Excel。2D和3D来源路径分列显示。"""
    print("📝 正在写入日志文件...")
    try:
        with open(log_file, "w", encoding="gbk", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["原始文件名", "ZIP文件名", "3D文件路径", "2D文件路径", "缺失的文件", "状态"])
            for res in result_log:
                found_3d = res.get("found_3d_path", "") or "无"
                found_2d = res.get("found_2d_path", "") or "无"
                missing = ";".join(res["files_missing"]) if res["files_missing"] else "无"
                status = res["status"]
                writer.writerow([res["original"], res["zip_file"], found_3d, found_2d, missing, status])
        print(f"✅ 日志已保存至: {log_file}")
        return True
    except Exception as e:
        print(f"⚠️ 日志文件写入失败: {str(e)}")
        return False


class StdoutRedirector:
    """重定向stdout到GUI日志队列。"""

    def __init__(self):
        self.buffer = []

    def write(self, message):
        self.buffer.append(message)
        if "\n" in message or len("".join(self.buffer)) > 1000:
            self.flush()

    def flush(self):
        if self.buffer:
            log_queue.put("".join(self.buffer))
            self.buffer = []


class SettingsWindow(ttk.Toplevel):
    """配置管理窗口。"""

    def __init__(self, parent, config_data, on_save_callback):
        super().__init__(parent)
        self.title("配置管理")
        self.geometry("800x900")
        self.minsize(700, 700)
        self.config_data = config_data.copy() if config_data else {}
        self.on_save_callback = on_save_callback

        self.transient(parent)
        self.grab_set()
        center_window(self, parent, 800, 900)
        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        main = ttk.Frame(self, padding=16)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)
        main.rowconfigure(5, weight=1)

        basic = ttk.Labelframe(main, text="基本设置", padding=12)
        basic.grid(row=0, column=0, sticky="ew")
        basic.columnconfigure(1, weight=1)

        self.output_entry = self._add_entry_row(basic, 0, "输出目录名", self.config_data.get("output_dir_name", "output"))
        self.list_entry = self._add_entry_row(
            basic,
            1,
            "原始清单文件",
            self.config_data.get("original_list_filename", "Original file list.txt"),
        )
        self.log_entry = self._add_entry_row(basic, 2, "日志文件名", self.config_data.get("log_filename", "log.csv"))

        perf = ttk.Labelframe(main, text="性能设置", padding=12)
        perf.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        perf.columnconfigure(1, weight=1)

        self.workers_entry = self._add_entry_row(perf, 0, "最大线程数", str(self.config_data.get("max_workers", 12)))
        self.retry_entry = self._add_entry_row(perf, 1, "重试次数", str(self.config_data.get("retry_attempts", 3)))

        self.rename_var = tk.BooleanVar(value=self.config_data.get("rename_3d_files", False))
        self.include_xt_var = tk.BooleanVar(value=self.config_data.get("include_xt_format", False))
        ttk.Checkbutton(
            perf,
            text="按照清单重命名3D文件",
            variable=self.rename_var,
            bootstyle="round-toggle",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            perf,
            text="包含 XT 格式3D文件",
            variable=self.include_xt_var,
            bootstyle="round-toggle",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        source_3d = ttk.Labelframe(main, text="3D源目录管理", padding=12)
        source_3d.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        source_3d.columnconfigure(0, weight=1)
        source_3d.rowconfigure(0, weight=1)

        text_outer_3d = ttk.Frame(source_3d)
        text_outer_3d.grid(row=0, column=0, sticky="nsew")
        text_outer_3d.columnconfigure(0, weight=1)
        text_outer_3d.rowconfigure(0, weight=1)

        self.source_3d_text = tk.Text(
            text_outer_3d,
            height=6,
            wrap="none",
            font=("Microsoft YaHei UI", 10),
            relief="solid",
            borderwidth=1,
        )
        self.source_3d_text.grid(row=0, column=0, sticky="nsew")
        yscroll_3d = ttk.Scrollbar(text_outer_3d, orient=tk.VERTICAL, command=self.source_3d_text.yview)
        yscroll_3d.grid(row=0, column=1, sticky="ns")
        xscroll_3d = ttk.Scrollbar(text_outer_3d, orient=tk.HORIZONTAL, command=self.source_3d_text.xview)
        xscroll_3d.grid(row=1, column=0, sticky="ew")
        self.source_3d_text.configure(yscrollcommand=yscroll_3d.set, xscrollcommand=xscroll_3d.set)

        for src_dir in self.config_data.get("source_dirs_3d", []):
            self.source_3d_text.insert(tk.END, src_dir + "\n")

        source_3d_buttons = ttk.Frame(source_3d)
        source_3d_buttons.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(source_3d_buttons, text="添加目录", bootstyle="secondary-outline", command=self._add_source_3d).pack(
            side=LEFT, padx=(0, 8)
        )
        ttk.Button(source_3d_buttons, text="删除当前行", bootstyle="secondary-outline", command=self._remove_source_3d).pack(
            side=LEFT, padx=(0, 8)
        )
        ttk.Button(source_3d_buttons, text="清空全部", bootstyle="secondary-outline", command=self._clear_source_3d).pack(
            side=LEFT
        )

        source_2d = ttk.Labelframe(main, text="2D源目录管理", padding=12)
        source_2d.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        source_2d.columnconfigure(0, weight=1)
        source_2d.rowconfigure(0, weight=1)

        text_outer_2d = ttk.Frame(source_2d)
        text_outer_2d.grid(row=0, column=0, sticky="nsew")
        text_outer_2d.columnconfigure(0, weight=1)
        text_outer_2d.rowconfigure(0, weight=1)

        self.source_2d_text = tk.Text(
            text_outer_2d,
            height=6,
            wrap="none",
            font=("Microsoft YaHei UI", 10),
            relief="solid",
            borderwidth=1,
        )
        self.source_2d_text.grid(row=0, column=0, sticky="nsew")
        yscroll_2d = ttk.Scrollbar(text_outer_2d, orient=tk.VERTICAL, command=self.source_2d_text.yview)
        yscroll_2d.grid(row=0, column=1, sticky="ns")
        xscroll_2d = ttk.Scrollbar(text_outer_2d, orient=tk.HORIZONTAL, command=self.source_2d_text.xview)
        xscroll_2d.grid(row=1, column=0, sticky="ew")
        self.source_2d_text.configure(yscrollcommand=yscroll_2d.set, xscrollcommand=xscroll_2d.set)

        for src_dir in self.config_data.get("source_dirs_2d", []):
            self.source_2d_text.insert(tk.END, src_dir + "\n")

        source_2d_buttons = ttk.Frame(source_2d)
        source_2d_buttons.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(source_2d_buttons, text="添加目录", bootstyle="secondary-outline", command=self._add_source_2d).pack(
            side=LEFT, padx=(0, 8)
        )
        ttk.Button(source_2d_buttons, text="删除当前行", bootstyle="secondary-outline", command=self._remove_source_2d).pack(
            side=LEFT, padx=(0, 8)
        )
        ttk.Button(source_2d_buttons, text="清空全部", bootstyle="secondary-outline", command=self._clear_source_2d).pack(
            side=LEFT
        )

        footer = ttk.Frame(self, padding=(16, 0, 16, 16))
        footer.grid(row=1, column=0, sticky="ew")
        ttk.Button(footer, text="取消", bootstyle="secondary-outline", command=self.destroy).pack(side=RIGHT)
        ttk.Button(footer, text="保存配置", bootstyle="success", command=self._save_config).pack(side=RIGHT, padx=(0, 8))

    def _add_entry_row(self, parent, row: int, label: str, value: str):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
        entry = ttk.Entry(parent)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        entry.insert(0, value)
        return entry

    def _add_source_3d(self):
        dir_path = filedialog.askdirectory(title="选择3D源目录")
        if dir_path:
            self.source_3d_text.insert(tk.END, dir_path + "\n")

    def _remove_source_3d(self):
        try:
            start = self.source_3d_text.index("insert linestart")
            end = self.source_3d_text.index("insert lineend +1c")
            self.source_3d_text.delete(start, end)
        except Exception:
            messagebox.showwarning("警告", "请先选择要删除的目录")

    def _clear_source_3d(self):
        if messagebox.askyesno("确认", "确定要清空所有3D源目录吗？"):
            self.source_3d_text.delete("1.0", tk.END)

    def _add_source_2d(self):
        dir_path = filedialog.askdirectory(title="选择2D源目录")
        if dir_path:
            self.source_2d_text.insert(tk.END, dir_path + "\n")

    def _remove_source_2d(self):
        try:
            start = self.source_2d_text.index("insert linestart")
            end = self.source_2d_text.index("insert lineend +1c")
            self.source_2d_text.delete(start, end)
        except Exception:
            messagebox.showwarning("警告", "请先选择要删除的目录")

    def _clear_source_2d(self):
        if messagebox.askyesno("确认", "确定要清空所有2D源目录吗？"):
            self.source_2d_text.delete("1.0", tk.END)

    def _save_config(self):
        try:
            max_workers = int(self.workers_entry.get())
            retry_attempts = int(self.retry_entry.get())

            if max_workers < 1 or retry_attempts < 1:
                messagebox.showerror("错误", "线程数和重试次数必须大于0")
                return

            content_3d = self.source_3d_text.get("1.0", "end").strip()
            source_dirs_3d = [line.strip() for line in content_3d.split("\n") if line.strip()] if content_3d else []

            content_2d = self.source_2d_text.get("1.0", "end").strip()
            source_dirs_2d = [line.strip() for line in content_2d.split("\n") if line.strip()] if content_2d else []

            self.config_data["output_dir_name"] = self.output_entry.get().strip()
            self.config_data["original_list_filename"] = self.list_entry.get().strip()
            self.config_data["log_filename"] = self.log_entry.get().strip()
            self.config_data["max_workers"] = max_workers
            self.config_data["retry_attempts"] = retry_attempts
            self.config_data["source_dirs_3d"] = source_dirs_3d
            self.config_data["source_dirs_2d"] = source_dirs_2d
            self.config_data["rename_3d_files"] = self.rename_var.get()
            self.config_data["include_xt_format"] = self.include_xt_var.get()
            apply_runtime_paths(self.config_data)

            if self.on_save_callback:
                self.on_save_callback(self.config_data)

            messagebox.showinfo("成功", "配置已保存并重新加载")
            self.destroy()
        except ValueError:
            messagebox.showerror("错误", "线程数和重试次数必须是整数")


class ListManagerWindow(ttk.Toplevel):
    """清单管理窗口。"""

    def __init__(self, parent, list_file_path, on_save_callback):
        super().__init__(parent)
        self.title("清单管理")
        self.geometry("820x620")
        self.minsize(680, 500)
        self.list_file_path = list_file_path
        self.on_save_callback = on_save_callback

        self.transient(parent)
        self.grab_set()
        center_window(self, parent, 820, 620)
        self._build_ui()
        self._load_file_content()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(16, 14, 16, 8))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            header,
            text=f"编辑清单文件: {os.path.basename(self.list_file_path)}",
            font=("Microsoft YaHei UI", 15, "bold"),
        ).pack(anchor="w")

        text_outer = ttk.Frame(self, padding=(16, 0, 16, 12))
        text_outer.grid(row=1, column=0, sticky="nsew")
        text_outer.columnconfigure(0, weight=1)
        text_outer.rowconfigure(0, weight=1)

        self.text_editor = tk.Text(text_outer, wrap="word", font=("Microsoft YaHei UI", 11), relief="solid", borderwidth=1)
        self.text_editor.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(text_outer, orient=tk.VERTICAL, command=self.text_editor.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text_editor.configure(yscrollcommand=scrollbar.set)

        footer = ttk.Frame(self, padding=(16, 0, 16, 16))
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Button(footer, text="取消", bootstyle="secondary-outline", command=self.destroy).pack(side=RIGHT)
        ttk.Button(footer, text="保存并退出", bootstyle="success", command=self._save_and_exit).pack(side=RIGHT, padx=(0, 8))

    def _load_file_content(self):
        try:
            if os.path.exists(self.list_file_path):
                with open(self.list_file_path, "r", encoding="utf-8-sig") as f:
                    content = f.read()
                self.text_editor.insert("1.0", content)
        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败: {str(e)}")
            self.destroy()

    def _save_and_exit(self):
        try:
            content = self.text_editor.get("1.0", "end-1c")
            with open(self.list_file_path, "w", encoding="utf-8-sig") as f:
                f.write(content)

            if self.on_save_callback:
                self.on_save_callback()

            messagebox.showinfo("成功", "清单文件已保存")
            self.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"保存文件失败: {str(e)}")

    def _on_closing(self):
        if messagebox.askyesno("确认", "确定要退出吗？未保存的更改将丢失。"):
            self.destroy()


class UpdateLogWindow(ttk.Toplevel):
    """更新日志窗口。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("更新日志")
        self.geometry("640x520")
        self.minsize(560, 420)

        self.transient(parent)
        self.grab_set()
        center_window(self, parent, 640, 520)
        self._build_ui()
        self._load_update_logs()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(16, 14, 16, 8))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="更新日志", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")

        body = ttk.Frame(self, padding=(16, 0, 16, 12))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.log_textbox = tk.Text(body, wrap="word", font=("Microsoft YaHei UI", 10), state="disabled", relief="solid")
        self.log_textbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.log_textbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_textbox.configure(yscrollcommand=scrollbar.set)

        footer = ttk.Frame(self, padding=(16, 0, 16, 16))
        footer.grid(row=2, column=0, sticky="ew")
        self.loading_var = tk.StringVar(value="正在获取更新日志...")
        ttk.Label(footer, textvariable=self.loading_var, bootstyle="secondary").pack(side=LEFT)
        ttk.Button(footer, text="关闭", bootstyle="primary", command=self.destroy).pack(side=RIGHT)

    def _load_update_logs(self):
        def fetch_logs():
            logs = get_update_logs(5)
            self.after(0, lambda: self._display_logs(logs))

        threading.Thread(target=fetch_logs, daemon=True).start()

    def _display_logs(self, logs):
        if not self.winfo_exists():
            return
        self.loading_var.set("")
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", tk.END)

        if not logs:
            self.log_textbox.insert(tk.END, "无法获取更新日志，请检查网络连接。")
            self.log_textbox.configure(state="disabled")
            return

        for log in logs:
            version = log.get("version", "")
            date = log.get("date", "")
            changelog = log.get("changelog", "")

            self.log_textbox.insert(tk.END, f"【版本 {version}】")
            self.log_textbox.insert(tk.END, f" ({date})\n" if date else "\n")
            self.log_textbox.insert(tk.END, "=" * 50 + "\n")
            self.log_textbox.insert(tk.END, f"{changelog}\n\n")

        self.log_textbox.configure(state="disabled")


class HelpWindow(ttk.Toplevel):
    """使用说明窗口 — 从 Gitee 加载 README.md 内容。"""

    README_URL = "https://gitee.com/caifugao110/obara-gunbag-fetcher/raw/master/README.md"

    def __init__(self, parent):
        super().__init__(parent)
        self.title("使用说明")
        self.geometry("780x620")
        self.minsize(640, 480)

        self.transient(parent)
        self.grab_set()
        center_window(self, parent, 780, 620)
        self._build_ui()
        self._load_readme()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(16, 14, 16, 8))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="使用说明", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")

        body = ttk.Frame(self, padding=(16, 0, 16, 12))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.textbox = tk.Text(body, wrap="word", font=("Microsoft YaHei UI", 10), state="disabled", relief="solid")
        self.textbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.textbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.textbox.configure(yscrollcommand=scrollbar.set)

        footer = ttk.Frame(self, padding=(16, 0, 16, 16))
        footer.grid(row=2, column=0, sticky="ew")
        self.loading_var = tk.StringVar(value="正在加载使用说明...")
        ttk.Label(footer, textvariable=self.loading_var, bootstyle="secondary").pack(side=LEFT)
        ttk.Button(footer, text="关闭", bootstyle="primary", command=self.destroy).pack(side=RIGHT)

    def _load_readme(self):
        def fetch():
            try:
                resp = requests.get(self.README_URL, timeout=10)
                resp.raise_for_status()
                content = resp.text
            except Exception as e:
                content = f"无法加载使用说明。\n\n错误信息: {str(e)}\n\n请访问项目主页查看: https://github.com/caifugao110/obara-gunbag-fetcher"
            self.after(0, lambda: self._display_content(content))

        threading.Thread(target=fetch, daemon=True).start()

    def _display_content(self, content):
        if not self.winfo_exists():
            return
        self.loading_var.set("")
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", tk.END)
        self.textbox.insert(tk.END, content)
        self.textbox.configure(state="disabled")


class GunbagFetcherApp(ttk.Window):
    """obara-gunbag-fetcher GUI界面。"""

    def __init__(self):
        super().__init__(themename="yeti")
        self.title(f"obara-gunbag-fetcher {VERSION}")
        self.geometry("1240x800")
        self.minsize(1000, 680)
        if ASSET_ICON.exists():
            self.iconbitmap(str(ASSET_ICON))

        self.config_path = None
        self.list_file_path = None
        self.config_data = None
        self.running = False
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.total_files = 0
        self.success_count = 0
        self.failure_count = 0
        self.start_time = 0
        self.original_stdout = sys.stdout
        self._closing = False

        self.theme_var = tk.StringVar(value="yeti")
        self.config_label_var = tk.StringVar(value="未选择")
        self.list_label_var = tk.StringVar(value="未选择")
        self.rename_checkbox_var = tk.BooleanVar(value=False)
        self.include_xt_checkbox_var = tk.BooleanVar(value=False)
        self.rebuild_index_var = tk.BooleanVar(value=True)
        self.progress_percent_var = tk.StringVar(value="0%")
        self.stats_var = tk.StringVar(value="已处理: 0 | 成功: 0 | 失败: 0 | 速度: 0 文件/秒")
        self.status_var = tk.StringVar(value="正在初始化")

        self._build_ui()
        self._redirect_stdout()
        self._listen_queues()
        self.after(200, self._auto_load_files)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(18, 14, 18, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title = ttk.Label(header, text="obara-gunbag-fetcher", font=("Microsoft YaHei UI", 22, "bold"))
        title.grid(row=0, column=0, sticky="w")
        meta = ttk.Label(header, text=f"{VERSION} 小原枪衣获取工具", bootstyle="secondary")
        meta.grid(row=1, column=0, sticky="w", pady=(2, 0))

        theme_bar = ttk.Frame(header)
        theme_bar.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Label(theme_bar, text="主题").pack(side=LEFT, padx=(0, 8))
        theme_box = ttk.Combobox(
            theme_bar,
            textvariable=self.theme_var,
            values=sorted(self.style.theme_names()),
            width=16,
            state="readonly",
        )
        theme_box.pack(side=LEFT)
        theme_box.bind("<<ComboboxSelected>>", self._change_theme)
        ttk.Button(theme_bar, text="GitHub", bootstyle="secondary-outline", command=lambda: webbrowser.open(PROJECT_URL)).pack(
            side=LEFT, padx=(8, 0)
        )
        ttk.Button(theme_bar, text="使用说明", bootstyle="secondary-outline", command=self._show_help).pack(
            side=LEFT, padx=(8, 0)
        )
        ttk.Button(theme_bar, text="更新日志", bootstyle="secondary-outline", command=self._show_update_log).pack(
            side=LEFT, padx=(8, 0)
        )
        ttk.Button(theme_bar, text="关于", bootstyle="secondary-outline", command=self.show_about).pack(side=LEFT, padx=(8, 0))

        main = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        main.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))

        controls = ttk.Frame(main, padding=12)
        main.add(controls, weight=1)
        results = ttk.Frame(main, padding=(10, 12, 12, 12))
        main.add(results, weight=4)

        self._build_controls(controls)
        self._build_results(results)

        footer = ttk.Frame(self, padding=(18, 0, 18, 14))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var, bootstyle="secondary").grid(row=0, column=0, sticky="w")

    def _build_controls(self, parent):
        parent.columnconfigure(0, weight=1)

        file_box = ttk.Labelframe(parent, text="文件设置", padding=12)
        file_box.grid(row=0, column=0, sticky="ew")
        file_box.columnconfigure(0, weight=1)

        self._add_file_picker(file_box, "配置文件", self.config_label_var, self._select_config, 0)
        self._add_file_picker(file_box, "原始清单", self.list_label_var, self._select_list_file, 1)

        option_box = ttk.Labelframe(parent, text="选项", padding=12)
        option_box.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        ttk.Checkbutton(
            option_box,
            text="按照清单重命名3D文件",
            variable=self.rename_checkbox_var,
            bootstyle="round-toggle",
            command=self._on_rename_checkbox_change,
        ).pack(anchor="w", pady=3)
        ttk.Checkbutton(
            option_box,
            text="包含 XT 格式3D文件",
            variable=self.include_xt_checkbox_var,
            bootstyle="round-toggle",
            command=self._on_include_xt_change,
        ).pack(anchor="w", pady=3)
        ttk.Checkbutton(
            option_box,
            text="重建2D/3D目录索引",
            variable=self.rebuild_index_var,
            bootstyle="round-toggle",
            command=self._on_rebuild_index_change,
        ).pack(anchor="w", pady=3)
        ttk.Label(
            option_box,
            text="既制焊枪关闭此开关,加快处理速度",
            font=("Arial", 9, "italic"),
            bootstyle="secondary",
        ).pack(anchor="w", padx=24, pady=(0, 6))

        action_box = ttk.Labelframe(parent, text="执行", padding=12)
        action_box.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        action_box.columnconfigure(0, weight=1)

        self.start_btn = ttk.Button(action_box, text="开始批量打包", bootstyle="success", command=self._start_process)
        self.start_btn.grid(row=0, column=0, sticky="ew")
        self.stop_btn = ttk.Button(action_box, text="停止处理", bootstyle="danger", command=self._stop_process, state="disabled")
        self.stop_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(action_box, text="配置管理", bootstyle="secondary-outline", command=self._open_settings).grid(
            row=2, column=0, sticky="ew", pady=(8, 0)
        )
        self.list_manager_btn = ttk.Button(
            action_box,
            text="清单管理",
            bootstyle="secondary-outline",
            command=self._open_list_manager,
            state="disabled",
        )
        self.list_manager_btn.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.open_output_btn = ttk.Button(
            action_box,
            text="打开输出目录",
            bootstyle="secondary-outline",
            command=self._open_output_dir,
            state="disabled",
        )
        self.open_output_btn.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.view_log_btn = ttk.Button(
            action_box,
            text="查看日志",
            bootstyle="secondary-outline",
            command=self._view_log,
            state="disabled",
        )
        self.view_log_btn.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(action_box, text="清空日志框", bootstyle="secondary-outline", command=self._clear_log).grid(
            row=6, column=0, sticky="ew", pady=(8, 0)
        )

    def _add_file_picker(self, parent, label, variable, command, row):
        group = ttk.Frame(parent)
        group.grid(row=row, column=0, sticky="ew", pady=(0, 10) if row == 0 else (0, 0))
        group.columnconfigure(0, weight=1)
        ttk.Label(group, text=label, font=("Microsoft YaHei UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(group, textvariable=variable, bootstyle="secondary", anchor="w", padding=(8, 8), relief="solid").grid(
            row=1, column=0, sticky="ew", pady=(4, 0), padx=(0, 8)
        )
        ttk.Button(group, text="选择", bootstyle="secondary-outline", command=command).grid(row=1, column=1, sticky="e", pady=(4, 0))

    def _build_results(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        progress_box = ttk.Labelframe(parent, text="处理进度", padding=12)
        progress_box.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        progress_box.columnconfigure(0, weight=1)

        progress_row = ttk.Frame(progress_box)
        progress_row.grid(row=0, column=0, sticky="ew")
        progress_row.columnconfigure(0, weight=1)
        self.progress_bar = ttk.Progressbar(progress_row, mode="determinate", maximum=100, value=0)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ttk.Label(progress_row, textvariable=self.progress_percent_var, width=6, anchor="e").grid(row=0, column=1)
        ttk.Label(progress_box, textvariable=self.stats_var, bootstyle="secondary").grid(row=1, column=0, sticky="w", pady=(8, 0))

        log_box = ttk.Labelframe(parent, text="处理日志", padding=12)
        log_box.grid(row=1, column=0, sticky="nsew")
        log_box.columnconfigure(0, weight=1)
        log_box.rowconfigure(0, weight=1)

        self.log_textbox = tk.Text(
            log_box,
            wrap="word",
            font=("Microsoft YaHei UI", 11),
            state="disabled",
            relief="solid",
            borderwidth=1,
        )
        self.log_textbox.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(log_box, orient=tk.VERTICAL, command=self.log_textbox.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.log_textbox.configure(yscrollcommand=yscroll.set)

    def _on_rename_checkbox_change(self):
        if self.config_data and self.config_path:
            self.config_data["rename_3d_files"] = self.rename_checkbox_var.get()
            save_configuration(self.config_path, self.config_data)
            self._clear_log()
            self.config_data = load_configuration(self.config_path)

    def _on_include_xt_change(self):
        if self.config_data and self.config_path:
            self.config_data["include_xt_format"] = self.include_xt_checkbox_var.get()
            save_configuration(self.config_path, self.config_data)
            self._clear_log()
            self.config_data = load_configuration(self.config_path)

    def _on_rebuild_index_change(self):
        global _INDEX_REBUILT_THIS_SESSION
        if not self.rebuild_index_var.get():
            _INDEX_REBUILT_THIS_SESSION = False
            _2D_INDEX_CACHE.clear()
            _3D_INDEX_CACHE.clear()
        if self.config_data and self.config_path:
            self.config_data["rebuild_index_before_pack"] = self.rebuild_index_var.get()
            save_configuration(self.config_path, self.config_data)
            self._clear_log()
            self.config_data = load_configuration(self.config_path)

    def _change_theme(self, _=None):
        self.style.theme_use(self.theme_var.get())

    def _redirect_stdout(self):
        self.original_stdout = sys.stdout
        sys.stdout = StdoutRedirector()

    def _drain_queues(self):
        max_messages_per_batch = 50
        log_count = 0

        while not log_queue.empty() and log_count < max_messages_per_batch:
            message = log_queue.get()
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert(tk.END, message)
            self.log_textbox.see(tk.END)
            self.log_textbox.configure(state="disabled")
            log_count += 1

        while not progress_queue.empty():
            item = progress_queue.get()
            if item[0] == "max":
                self.total_files = item[1]
                self.success_count = 0
                self.failure_count = 0
                self.start_time = time.time()
                self.progress_bar.configure(value=0)
                self.progress_percent_var.set("0%")
                self.stats_var.set("已处理: 0 | 成功: 0 | 失败: 0 | 速度: 0 文件/秒")
            elif item[0] == "update":
                current = item[1]
                self.success_count = item[2]
                self.failure_count = item[3]
                speed = item[4]

                if self.total_files > 0:
                    percentage = (current / self.total_files) * 100
                    self.progress_bar.configure(value=percentage)
                    self.progress_percent_var.set(f"{int(percentage)}%")

                self.stats_var.set(
                    f"已处理: {current} | 成功: {self.success_count} | 失败: {self.failure_count} | 速度: {speed:.1f} 文件/秒"
                )
            elif item[0] == "complete":
                if hasattr(sys.stdout, "flush"):
                    sys.stdout.flush()

                self.running = False
                self.start_btn.configure(state="normal")
                self.stop_btn.configure(state="disabled")
                self.list_manager_btn.configure(state="normal")
                self.status_var.set("任务完成" if item[1] else "任务已停止或失败")

                if item[1]:
                    self.open_output_btn.configure(state="normal")
                    self.view_log_btn.configure(state="normal")

    def _listen_queues(self):
        if self._closing:
            return
        self._drain_queues()
        delay = 20 if not log_queue.empty() else 100
        self.after(delay, self._listen_queues)

    def _auto_load_files(self):
        self._clear_log()
        root_path = get_root_path()
        default_config = os.path.join(root_path, "config.ini")

        if os.path.exists(default_config):
            self.config_path = default_config
            self.config_label_var.set(os.path.basename(default_config))
            self.config_data = load_configuration(default_config)

            if self.config_data:
                self.rename_checkbox_var.set(self.config_data.get("rename_3d_files", False))
                self.include_xt_checkbox_var.set(self.config_data.get("include_xt_format", False))
                self.rebuild_index_var.set(self.config_data.get("rebuild_index_before_pack", True))

                default_list = self.config_data.get("list_file")
                if os.path.exists(default_list):
                    self._clear_log()
                    self.list_file_path = default_list
                    self.list_label_var.set(os.path.basename(default_list))
                    self.list_manager_btn.configure(state="normal")

                self.start_btn.configure(state="normal")
                self.status_var.set("配置已加载")
        else:
            self.status_var.set("请选择配置文件")

    def _select_config(self):
        file_path = filedialog.askopenfilename(title="选择配置文件", filetypes=[("INI文件", "*.ini"), ("所有文件", "*.*")])

        if file_path:
            self._clear_log()
            self.config_path = file_path
            self.config_label_var.set(os.path.basename(file_path))
            self.config_data = load_configuration(file_path)

            if self.config_data:
                self.rename_checkbox_var.set(self.config_data.get("rename_3d_files", False))
                self.include_xt_checkbox_var.set(self.config_data.get("include_xt_format", False))
                self.rebuild_index_var.set(self.config_data.get("rebuild_index_before_pack", True))

                list_file = self.config_data.get("list_file")
                if os.path.exists(list_file):
                    self._clear_log()
                    self.list_file_path = list_file
                    self.list_label_var.set(os.path.basename(list_file))
                    self.list_manager_btn.configure(state="normal")

                self.start_btn.configure(state="normal")
                self.status_var.set("配置已加载")
            else:
                self.start_btn.configure(state="disabled")
                self.status_var.set("配置加载失败")

    def _select_list_file(self):
        file_path = filedialog.askopenfilename(
            title="选择原始清单文件",
            filetypes=[("TXT文件", "*.txt"), ("CSV文件", "*.csv"), ("所有文件", "*.*")],
        )

        if file_path:
            self._clear_log()
            self.list_file_path = file_path
            self.list_label_var.set(os.path.basename(file_path))
            self.list_manager_btn.configure(state="normal")

            if self.config_data and self.config_path:
                self.config_data["original_list_filename"] = os.path.basename(file_path)
                self.config_data["list_file"] = file_path
                save_configuration(self.config_path, self.config_data)
                self.config_data = load_configuration(self.config_path)
                if self.config_data:
                    self.config_data["list_file"] = file_path
                    self.rename_checkbox_var.set(self.config_data.get("rename_3d_files", False))
                    self.include_xt_checkbox_var.set(self.config_data.get("include_xt_format", False))
                    self.rebuild_index_var.set(self.config_data.get("rebuild_index_before_pack", True))

            if self.config_data:
                self.start_btn.configure(state="normal")

    def _open_settings(self):
        if not self.config_data:
            self.config_data = {
                "output_dir_name": "output",
                "original_list_filename": "Original file list.txt",
                "log_filename": "log.csv",
                "max_workers": 12,
                "retry_attempts": 3,
                "source_dirs_3d": [],
                "source_dirs_2d": [],
                "rename_3d_files": False,
                "include_xt_format": False,
            }

        settings_window = SettingsWindow(self, self.config_data, self._on_settings_saved)
        settings_window.focus()

    def _on_settings_saved(self, config_data):
        self._clear_log()
        if not self.config_path:
            self.config_path = os.path.join(get_root_path(), "config.ini")

        save_configuration(self.config_path, config_data)
        self.config_data = load_configuration(self.config_path)

        if self.config_data:
            self.rename_checkbox_var.set(self.config_data.get("rename_3d_files", False))
            self.include_xt_checkbox_var.set(self.config_data.get("include_xt_format", False))
            self.rebuild_index_var.set(self.config_data.get("rebuild_index_before_pack", True))

            list_file = self.config_data.get("list_file")
            if os.path.exists(list_file):
                self._clear_log()
                self.list_file_path = list_file
                self.list_label_var.set(os.path.basename(list_file))
                self.list_manager_btn.configure(state="normal")

            self.start_btn.configure(state="normal")
            self.config_label_var.set(os.path.basename(self.config_path))
            self.status_var.set("配置已保存")

    def _open_list_manager(self):
        if not self.list_file_path:
            messagebox.showwarning("警告", "请先选择清单文件")
            return

        list_manager_window = ListManagerWindow(self, self.list_file_path, self._on_list_saved)
        list_manager_window.focus()

    def _on_list_saved(self):
        print(f"✅ 清单文件已保存: {self.list_file_path}")
        self._clear_log()
        print("🔄 正在重新加载清单文件...")

        if self.config_data:
            original_files = read_original_file_list(self.list_file_path)
            if original_files:
                print(f"✅ 清单文件重新加载成功，共 {len(original_files)} 个文件")
            else:
                print("⚠️ 清单文件重新加载失败")

    def _start_process(self):
        if not self.config_data or not self.list_file_path:
            messagebox.showwarning("警告", "请先选择配置文件和清单文件")
            return

        self._clear_log()

        output_dir = self.config_data.get("output_dir")
        ensure_output_directory(output_dir)

        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.open_output_btn.configure(state="disabled")
        self.view_log_btn.configure(state="disabled")
        self.list_manager_btn.configure(state="disabled")

        self.progress_bar.configure(value=0)
        self.progress_percent_var.set("0%")
        self.stats_var.set("已处理: 0 | 成功: 0 | 失败: 0 | 速度: 0 文件/秒")
        self.status_var.set("任务运行中")
        self.stop_event.clear()

        if self.config_data is not None:
            self.config_data["include_xt_format"] = self.include_xt_checkbox_var.get()
            self.config_data["rename_3d_files"] = self.rename_checkbox_var.get()
            self.config_data["rebuild_index_before_pack"] = self.rebuild_index_var.get()
            self.config_data["list_file"] = self.list_file_path
            if self.config_path:
                save_configuration(self.config_path, self.config_data)

        self.worker_thread = threading.Thread(
            target=worker,
            args=(self.config_data, self._update_progress, self.stop_event),
            daemon=True,
        )
        self.worker_thread.start()

    def _stop_process(self):
        if messagebox.askyesno("确认", "确定要停止当前操作吗？"):
            self.stop_event.set()
            self.stop_btn.configure(state="disabled")
            self.status_var.set("正在停止任务")

    def _update_progress(self, current, total):
        pass

    def _open_output_dir(self):
        if self.config_data:
            output_dir = self.config_data.get("output_dir")
            if os.path.exists(output_dir):
                open_path(output_dir)
            else:
                messagebox.showwarning("警告", f"输出目录不存在: {output_dir}")

    def _view_log(self):
        if self.config_data:
            log_file = self.config_data.get("log_file")
            if os.path.exists(log_file):
                open_path(log_file)
            else:
                messagebox.showwarning("警告", f"日志文件不存在: {log_file}")

    def _show_update_log(self):
        update_log_window = UpdateLogWindow(self)
        update_log_window.focus()

    def _show_help(self):
        help_window = HelpWindow(self)
        help_window.focus()

    def _clear_log(self):
        try:
            self.log_textbox.configure(state="normal")
            self.log_textbox.delete("1.0", tk.END)
            self.log_textbox.configure(state="disabled")
        except Exception:
            pass

    def show_about(self):
        dialog = ttk.Toplevel(self)
        dialog.title("关于 obara-gunbag-fetcher")
        dialog.geometry("500x280")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        center_window(dialog, self, 500, 280)

        container = ttk.Frame(dialog, padding=22)
        container.pack(fill=BOTH, expand=YES)
        ttk.Label(container, text="obara-gunbag-fetcher", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
        ttk.Label(container, text=f"版本 {VERSION}", bootstyle="secondary").pack(anchor="w", pady=(4, 0))
        ttk.Label(container, text=f"作者：{__author__}", bootstyle="secondary").pack(anchor="w", pady=(8, 0))
        ttk.Label(container, text="开源协议：MIT", bootstyle="secondary").pack(anchor="w", pady=(4, 0))
        link = ttk.Label(container, text=PROJECT_URL, bootstyle="primary", cursor="hand2")
        link.pack(anchor="w", pady=(14, 0))
        link.bind("<Button-1>", lambda _: webbrowser.open(PROJECT_URL))
        ttk.Button(container, text="关闭", bootstyle="primary", command=dialog.destroy).pack(anchor="e", pady=(24, 0))

    def on_closing(self):
        if self.running:
            if not messagebox.askyesno("确认", "当前正在处理文件，确定要退出吗？"):
                return
            self.stop_event.set()

        self._closing = True
        if hasattr(sys.stdout, "flush"):
            sys.stdout.flush()
        self._drain_queues()
        sys.stdout = self.original_stdout
        self.destroy()


def main() -> None:
    app = GunbagFetcherApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
