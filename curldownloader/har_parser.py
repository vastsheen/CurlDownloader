"""Extract downloadable m3u8 requests from browser HAR files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .curl_parser import CurlRequest


PRIMARY_HEADER_NAMES = {
    "cookie",
    "origin",
    "referer",
    "user-agent",
}

# These headers describe a single browser transport request, rather than the
# authorization context required to retrieve the media playlist.
TRANSPORT_HEADER_NAMES = {
    "accept-encoding",
    "cache-control",
    "connection",
    "content-encoding",
    "content-length",
    "host",
    "if-match",
    "if-modified-since",
    "if-none-match",
    "if-range",
    "if-unmodified-since",
    "pragma",
    "range",
    "transfer-encoding",
}


def _header_map(headers: list[dict[str, Any]]) -> dict[str, str]:
    """Convert HAR header objects to a case-insensitive mapping."""
    mapped: dict[str, str] = {}
    for header in headers:
        name = str(header.get("name", "")).strip()
        value = str(header.get("value", "")).strip()
        if name and value:
            mapped[name.lower()] = value
    return mapped


def _is_success_status(status: Any) -> bool:
    """Return whether a HAR response status is a successful HTTP code."""
    return isinstance(status, int) and 200 <= status < 400


def _is_m3u8_entry(url: str, mime_type: str, text: str) -> bool:
    """Identify m3u8 entries by URL, MIME type, or response prefix."""
    lower_path = urlsplit(url).path.lower()
    lower_mime = mime_type.lower()
    return (
        lower_path.endswith(".m3u8")
        or "mpegurl" in lower_mime
        or text.lstrip().lower().startswith("#extm3u")
    )


def extract_m3u8_requests_from_har(path: Path) -> list[CurlRequest]:
    """Extract successful m3u8 requests from a HAR file."""
    try:
        with path.open("r", encoding="utf-8-sig") as file:
            har = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"HAR JSON 解析失败: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"HAR 文件读取失败: {exc}") from exc

    entries = har.get("log", {}).get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("HAR 格式不正确: log.entries 不是列表")

    requests: list[CurlRequest] = []
    seen_urls: set[str] = set()
    skipped_failed = 0

    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})
        url = str(request.get("url", "")).strip()
        content = response.get("content", {})
        mime_type = str(content.get("mimeType", ""))
        text = str(content.get("text", ""))

        if not _is_m3u8_entry(url, mime_type, text):
            continue

        if not _is_success_status(response.get("status")):
            skipped_failed += 1
            continue

        if url in seen_urls:
            continue

        headers = _header_map(request.get("headers", []))
        extra_headers: dict[str, str] = {}
        for name, value in headers.items():
            if (
                name in PRIMARY_HEADER_NAMES
                or name in TRANSPORT_HEADER_NAMES
                or name.startswith(":")
            ):
                continue
            extra_headers[name] = value

        requests.append(
            CurlRequest(
                url=url,
                referer=headers.get("referer", ""),
                cookie=headers.get("cookie", ""),
                user_agent=headers.get("user-agent", ""),
                origin=headers.get("origin", ""),
                extra_headers=extra_headers,
            )
        )
        seen_urls.add(url)

    if not requests:
        suffix = "，已跳过失败请求" if skipped_failed else ""
        raise ValueError(f"HAR 中没有找到成功的 m3u8 请求{suffix}")

    return requests


def extract_media_requests_from_har(path: Path) -> list[CurlRequest]:
    """Extract complete direct MP4 tracks represented by successful HAR ranges.

    Browsers often request only portions of a media resource. This function
    groups those requests by URL and returns one request per distinct MP4
    track, allowing yt-dlp to fetch the complete resource from the signed URL.
    """
    try:
        with path.open("r", encoding="utf-8-sig") as file:
            har = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"HAR JSON 解析失败: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"HAR 文件读取失败: {exc}") from exc

    entries = har.get("log", {}).get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("HAR 格式不正确: log.entries 不是列表")

    tracks: dict[str, dict[str, Any]] = {}
    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})
        content = response.get("content", {}) or {}
        url = str(request.get("url", "")).strip()
        mime = str(content.get("mimeType", "")).lower()
        if not url or "video/mp4" not in mime or not _is_success_status(response.get("status")):
            continue

        response_headers = _header_map(response.get("headers", []))
        content_range = response_headers.get("content-range", "")
        # Accept only byte-range MP4 responses that reveal the full resource size.
        match = re.fullmatch(r"bytes\s+\d+-\d+/(\d+)", content_range, re.IGNORECASE)
        if not match:
            continue

        headers = _header_map(request.get("headers", []))
        track = tracks.setdefault(url, {"size": int(match.group(1)), "headers": headers})
        if track["size"] != int(match.group(1)):
            continue
        # Prefer the first request's auth headers; ignore the partial Range.

    requests: list[CurlRequest] = []
    for url, track in tracks.items():
        headers = track["headers"]
        extra_headers = {
            name: value
            for name, value in headers.items()
            if name not in PRIMARY_HEADER_NAMES
            and name not in TRANSPORT_HEADER_NAMES
            and name not in {"accept", "accept-language", "priority", "sec-ch-ua",
                             "sec-ch-ua-mobile", "sec-ch-ua-platform", "sec-fetch-dest",
                             "sec-fetch-mode", "sec-fetch-site"}
            and not name.startswith(":")
        }
        requests.append(
            CurlRequest(
                url=url,
                referer=headers.get("referer", ""),
                cookie=headers.get("cookie", ""),
                user_agent=headers.get("user-agent", ""),
                origin=headers.get("origin", ""),
                extra_headers=extra_headers,
                merge_output_format="mp4" if len(tracks) > 1 else "",
            )
        )

    if not requests:
        raise ValueError("HAR 中没有找到带 Content-Range 的成功 MP4 请求")
    if len(requests) > 1:
        # These are independent audio/video tracks from one playback session.
        requests = [
            CurlRequest(
                url=requests[0].url,
                referer=requests[0].referer,
                cookie=requests[0].cookie,
                user_agent=requests[0].user_agent,
                origin=requests[0].origin,
                merge_output_format="mp4",
                extra_urls=[request.url for request in requests[1:]],
            )
        ]
    return requests


def to_curl_text(requests: list[CurlRequest]) -> str:
    """Render extracted requests as cURL blocks supported by the app."""
    blocks: list[str] = []
    for request in requests:
        parts = [f'curl.exe "{request.url}"']
        if request.referer:
            parts.append(f'-H "referer: {request.referer}"')
        if request.user_agent:
            parts.append(f'-H "user-agent: {request.user_agent}"')
        if request.origin:
            parts.append(f'-H "origin: {request.origin}"')
        if request.cookie:
            parts.append(f'-H "cookie: {request.cookie}"')
        for name, value in request.extra_headers.items():
            parts.append(f'-H "{name}: {value}"')
        blocks.append(" ".join(parts))
    return "\n\n".join(blocks)
