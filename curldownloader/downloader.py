"""调用内嵌或本地 yt-dlp 执行下载。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .curl_parser import CurlRequest, iter_download_headers
from .paths import resource_path
from .progress_parser import DownloadProgress, parse_ytdlp_line


LogCallback = Callable[[str], None]
ProgressCallback = Callable[[DownloadProgress], None]

INCOMPLETE_SUFFIXES = (".part", ".ytdl", ".temp", ".frag")


def is_incomplete_download_file(path: Path) -> bool:
    """判断是否为下载中的临时文件。"""
    name = path.name.lower()
    if name.endswith(INCOMPLETE_SUFFIXES):
        return True
    return ".part" in name or ".ytdl" in name


def has_file_name_conflict(output_dir: Path, output_name: str) -> bool:
    """检查目录中是否已有同名成品文件。"""
    if not output_dir.is_dir():
        return False

    for path in output_dir.glob(f"{output_name}.*"):
        if path.is_file() and not is_incomplete_download_file(path):
            return True
    return False


def resolve_unique_output_name(output_dir: Path, output_name: str, *, resume: bool) -> str:
    """文件名冲突时自动追加 _{序号}，断点续传时保留原文件名。"""
    if resume and find_partial_files(output_dir, output_name):
        return output_name

    if not has_file_name_conflict(output_dir, output_name):
        return output_name

    no = 1
    while has_file_name_conflict(output_dir, f"{output_name}_{no}"):
        no += 1
    return f"{output_name}_{no}"


def find_next_numeric_output_start(output_dir: Path) -> int:
    """Find the next numeric output name based on existing file stems."""
    if not output_dir.is_dir():
        return 1

    max_no = 0
    for path in output_dir.iterdir():
        if not path.is_file():
            continue
        stem = path.stem
        if stem.isdecimal():
            max_no = max(max_no, int(stem))
    return max_no + 1


def build_batch_output_names(output_dir: Path, total: int) -> list[str]:
    """为本轮批量任务生成编号，位数按最大编号补零：9 个任务为 1..9，10 个为 01..10，100 个为 001..100。"""
    if total <= 0:
        return []

    start = find_next_numeric_output_start(output_dir)
    width = len(str(start + total - 1))
    return [str(start + offset).zfill(width) for offset in range(total)]


def find_ytdlp() -> Path:
    """定位 yt-dlp 可执行文件。"""
    candidates = [
        resource_path("bin", "yt-dlp.exe"),
        Path(sys.executable).resolve().parent / "bin" / "yt-dlp.exe",
        Path(sys.executable).resolve().parent / "yt-dlp.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path

    found = shutil.which("yt-dlp")
    if found:
        return Path(found)

    raise FileNotFoundError("未找到 yt-dlp.exe，请重新打包或安装 yt-dlp 到 PATH")


def find_ffmpeg() -> str | None:
    """查找 ffmpeg，HLS 合并通常需要。"""
    bundled = resource_path("bin", "ffmpeg.exe")
    if bundled.is_file():
        return str(bundled)
    return shutil.which("ffmpeg")


def find_partial_files(output_dir: Path, output_name: str) -> list[Path]:
    """查找可续传的未完成文件（.part / .ytdl）。"""
    if not output_dir.is_dir():
        return []

    patterns = [
        f"{output_name}.*.part",
        f"{output_name}.*.ytdl",
        f"{output_name}.part",
        f"{output_name}.ytdl",
    ]
    found: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for path in output_dir.glob(pattern):
            if path in seen or not path.is_file():
                continue
            if not is_incomplete_download_file(path):
                continue
            seen.add(path)
            found.append(path)
    return found


def build_ytdlp_command(
    request: CurlRequest,
    output_dir: Path,
    output_name: str,
    *,
    resume: bool = True,
) -> list[str]:
    """构建 yt-dlp 命令参数列表。"""
    ytdlp = find_ytdlp()
    output_template = str(output_dir / f"{output_name}.%(ext)s")

    cmd = [
        str(ytdlp),
        "--no-playlist",
        "--no-check-certificates",
        "--progress",
        "--newline",
        "-o",
        output_template,
    ]

    if resume:
        cmd.extend(
            [
                "--continue",
                "--no-overwrites",
                "--fragment-retries",
                "10",
                "--retries",
                "10",
                "--file-access-retries",
                "3",
            ]
        )

    for name, value in iter_download_headers(request):
        cmd.extend(["--add-header", f"{name}:{value}"])

    ffmpeg = find_ffmpeg()
    if ffmpeg:
        cmd.extend(["--ffmpeg-location", str(Path(ffmpeg).parent)])
    else:
        cmd.append("--hls-use-mpegts")

    if request.merge_output_format:
        cmd.extend(["--merge-output-format", request.merge_output_format])

    if request.extra_urls:
        cmd.extend(["-f", "bestvideo+bestaudio/best"])
    cmd.append(request.url)
    cmd.extend(request.extra_urls)
    return cmd


def download_with_ytdlp(
    request: CurlRequest,
    output_dir: Path,
    output_name: str = "video",
    log: LogCallback | None = None,
    on_progress: ProgressCallback | None = None,
    *,
    resume: bool = True,
) -> subprocess.CompletedProcess[str]:
    """执行 yt-dlp 下载并实时输出日志。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    resolved_name = resolve_unique_output_name(output_dir, output_name, resume=resume)
    if resolved_name != output_name and log:
        log(f"检测到重名，自动改用文件名: {resolved_name}")

    if resume:
        partials = find_partial_files(output_dir, resolved_name)
        if log:
            if partials:
                names = ", ".join(p.name for p in partials[:5])
                suffix = " ..." if len(partials) > 5 else ""
                log(f"检测到未完成文件，将尝试续传: {names}{suffix}")
            elif resolved_name == output_name:
                log("断点续传已开启（同目录同文件名时可续传）")

    cmd = build_ytdlp_command(request, output_dir, resolved_name, resume=resume)

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
        progress = parse_ytdlp_line(line)
        if progress and on_progress:
            on_progress(progress)
        if log:
            log(line.rstrip())

    returncode = process.wait()
    if returncode != 0:
        raise RuntimeError(f"yt-dlp 下载失败，退出码 {returncode}")

    return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr="")
