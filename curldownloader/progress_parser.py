"""解析 yt-dlp 控制台输出中的进度信息。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class DownloadProgress:
    """下载进度快照。"""

    percent: float | None
    status: str
    detail: str


DOWNLOAD_LINE = re.compile(
    r"\[download\]\s+(?P<pct>[\d.]+)%\s+of\s+(?P<total>.+?)\s+at\s+(?P<speed>.+?)\s+ETA\s+(?P<eta>.+)$"
)


def parse_ytdlp_line(line: str) -> DownloadProgress | None:
    """从 yt-dlp 单行日志解析进度，无法识别时返回 None。"""
    text = line.strip()
    if not text:
        return None

    if text.startswith("[Merger]"):
        return DownloadProgress(99.0, "正在合并", "ffmpeg 合并音视频…")

    if text.startswith("[ExtractAudio]"):
        return DownloadProgress(95.0, "处理音频", text.replace("[ExtractAudio]", "").strip())

    if text.startswith("[FixupM3u8]"):
        return DownloadProgress(None, "处理流", "修正 HLS 分片…")

    if text.startswith("[download] Destination:"):
        return DownloadProgress(0.0, "准备下载", "已连接，等待数据…")

    match = DOWNLOAD_LINE.search(text)
    if match:
        pct = float(match.group("pct"))
        total = match.group("total").strip()
        speed = match.group("speed").strip()
        eta = match.group("eta").strip()
        status = "下载完成" if pct >= 100 else "正在下载"
        detail = f"{speed} · ETA {eta} · {total}"
        return DownloadProgress(pct, status, detail)

    if text.startswith("[download]") and "100%" in text:
        return DownloadProgress(100.0, "下载完成", "等待合并或收尾…")

    return None
