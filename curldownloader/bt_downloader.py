"""调用 aria2c 执行磁力链接或种子下载。"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .paths import resource_path
from .progress_parser import DownloadProgress


LogCallback = Callable[[str], None]
ProgressCallback = Callable[[DownloadProgress], None]


DEFAULT_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.dler.org:6969/announce",
    "udp://open.demonii.com:1337/announce",
    "http://tracker.opentrackr.org:1337/announce",
    "https://tracker.tamersunion.org:443/announce",
]


ARIA_PROGRESS = re.compile(
    r"\[#(?P<gid>[0-9a-f]+)\s+"
    r"(?P<done>[\d.]+[KMGTP]?i?B)/(?P<total>[\d.]+[KMGTP]?i?B)"
    r"\((?P<pct>\d+)%\)\s+"
    r"CN:(?P<cn>\d+)\s+SD:(?P<sd>\d+)\s+DL:(?P<dl>[\d.]+[KMGTP]?i?B)"
)


def find_aria2c() -> Path:
    """定位 aria2c 可执行文件。"""
    candidates = [
        resource_path("bin", "aria2c.exe"),
        Path(sys.executable).resolve().parent / "bin" / "aria2c.exe",
        Path(sys.executable).resolve().parent / "aria2c.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path

    found = shutil.which("aria2c")
    if found:
        return Path(found)

    raise FileNotFoundError("未找到 aria2c.exe，请放到 bin 目录或安装 aria2 到 PATH")


def is_magnet(text: str) -> bool:
    """判断是否为磁力链接。"""
    return text.strip().lower().startswith("magnet:?")


def is_torrent_file(text: str) -> bool:
    """判断是否为本地种子文件路径。"""
    path_text = text.strip().strip('"')
    return path_text.lower().endswith(".torrent") and Path(path_text).is_file()


def parse_aria2_line(line: str) -> DownloadProgress | None:
    """从 aria2c 单行日志解析 BT 下载进度。"""
    text = line.strip()
    if not text:
        return None

    if "Downloading BitTorrent Metalink" in text or "Metadata download" in text:
        return DownloadProgress(None, "获取资源信息", "正在通过 DHT / tracker 获取种子元数据")

    match = ARIA_PROGRESS.search(text)
    if match:
        pct = float(match.group("pct"))
        done = match.group("done")
        total = match.group("total")
        dl = match.group("dl")
        cn = match.group("cn")
        sd = match.group("sd")
        detail = f"{done}/{total} · {dl}/s · 连接 {cn} · 种子 {sd}"
        return DownloadProgress(pct, "正在下载", detail)

    if "download completed" in text.lower() or "Download complete" in text:
        return DownloadProgress(100.0, "下载完成", "BT 任务已完成")

    if "No URI to download" in text:
        return DownloadProgress(None, "资源不可用", "没有可下载地址")

    return None


def build_aria2_command(source: str, output_dir: Path) -> list[str]:
    """构建 aria2c BT 下载命令。"""
    aria2c = find_aria2c()
    source = source.strip().strip('"')

    return [
        str(aria2c),
        "--dir",
        str(output_dir),
        "--continue=true",
        "--enable-dht=true",
        "--enable-dht6=true",
        "--enable-peer-exchange=true",
        "--bt-enable-lpd=true",
        "--bt-save-metadata=true",
        "--bt-metadata-only=false",
        "--bt-max-peers=120",
        "--bt-request-peer-speed-limit=0",
        "--max-overall-download-limit=0",
        "--max-download-limit=0",
        "--max-concurrent-downloads=3",
        "--seed-time=0",
        "--summary-interval=1",
        "--console-log-level=notice",
        "--bt-tracker",
        ",".join(DEFAULT_TRACKERS),
        source,
    ]


def download_with_aria2(
    source: str,
    output_dir: Path,
    log: LogCallback | None = None,
    on_progress: ProgressCallback | None = None,
) -> subprocess.CompletedProcess[str]:
    """执行 aria2c 下载并实时输出日志。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_aria2_command(source, output_dir)

    if log:
        log("执行命令:")
        log(" ".join(f'"{part}"' if " " in part else part for part in cmd))
        log("")

    env = os.environ.copy()
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        creationflags=creationflags,
    )

    assert process.stdout is not None
    for line in process.stdout:
        progress = parse_aria2_line(line)
        if progress and on_progress:
            on_progress(progress)
        if log:
            log(line.rstrip())

    returncode = process.wait()
    if returncode != 0:
        raise RuntimeError(f"aria2c 下载失败，退出码 {returncode}")

    return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr="")
