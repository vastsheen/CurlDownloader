"""解析浏览器 Copy as cURL 命令，提取 URL 与关键请求头。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class CurlRequest:
    """cURL 解析结果。"""

    url: str
    referer: str = ""
    cookie: str = ""
    user_agent: str = ""
    origin: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)
    # Optional output container for direct media resource downloads.
    merge_output_format: str = ""
    # Multiple direct media URLs belonging to a single presentation.
    extra_urls: list[str] = field(default_factory=list)


DOWNLOAD_HEADER_KEYS = {
    "accept",
    "accept-language",
    "origin",
    "referer",
    "sec-ch-ua",
    "sec-ch-ua-mobile",
    "sec-ch-ua-platform",
    "sec-fetch-dest",
    "sec-fetch-mode",
    "sec-fetch-site",
}


def _is_windows_cmd_curl(raw: str) -> bool:
    """判断是否为 Windows CMD 导出的 cURL。"""
    return "^" in raw and (
        '^"' in raw
        or re.search(r"\^\s*$", raw, re.MULTILINE) is not None
        or re.search(r"\^\s*\r?\n", raw) is not None
    )


def _unescape_windows_cmd(text: str) -> str:
    """还原 CMD 中的 ^ 转义（^\"、^\\、行尾 ^ 续行等）。"""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\^\s*\n", " ", text)
    text = re.sub(r"\^\s*$", " ", text, flags=re.MULTILINE)

    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "^" and i + 1 < len(text):
            out.append(text[i + 1])
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _unquote(token: str) -> str:
    """去掉 shell 引号并处理常见转义。"""
    text = token.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        body = text[1:-1]
        if text[0] == "'":
            return body.replace("\\'", "'").replace("\\\\", "\\")
        return body.replace('\\"', '"').replace("\\\\", "\\")
    return text


def _tokenize(line: str) -> list[str]:
    """按 shell 规则切分 curl 参数。"""
    tokens: list[str] = []
    current = ""
    quote: str | None = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\" and i + 1 < len(line):
                current += ch + line[i + 1]
                i += 2
                continue
            current += ch
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            current += ch
            i += 1
            continue
        if ch.isspace():
            if current:
                tokens.append(current)
                current = ""
            i += 1
            continue
        current += ch
        i += 1
    if current:
        tokens.append(current)
    return tokens


def _normalize(raw: str) -> str:
    """合并续行、处理 CMD/bash 转义并压缩空白。"""
    text = raw.replace("\r\n", "\n").strip()
    if not text:
        return ""

    if _is_windows_cmd_curl(text):
        text = _unescape_windows_cmd(text)

    text = re.sub(r"\\\s*\n", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_curl(raw: str) -> CurlRequest:
    """解析 cURL 命令，返回 URL 与 Referer/Cookie/User-Agent 等。"""
    text = _normalize(raw)
    if not text:
        raise ValueError("请输入 cURL 命令")

    text = re.sub(r"^curl(?:\.exe)?\s+", "", text, flags=re.IGNORECASE)
    tokens = _tokenize(text)

    referer = ""
    cookie = ""
    user_agent = ""
    origin = ""
    url = ""
    extra_headers: dict[str, str] = {}

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        lower = tok.lower()

        def read_value() -> str:
            nonlocal i
            if i + 1 >= len(tokens) or tokens[i + 1].startswith("-"):
                return ""
            i += 1
            return _unquote(tokens[i])

        candidate = _unquote(tok)
        if re.match(r"^https?://", candidate, re.IGNORECASE):
            url = candidate
            i += 1
            continue

        if lower in ("-h", "--header"):
            header_value = read_value()
            if ":" in header_value:
                key, value = header_value.split(":", 1)
                key_stripped = key.strip()
                key_lower = key_stripped.lower()
                value = value.strip()

                if key_lower == "referer":
                    referer = value
                elif key_lower == "cookie":
                    cookie = value
                elif key_lower == "user-agent":
                    user_agent = value
                elif key_lower == "origin":
                    origin = value
                elif key_lower in DOWNLOAD_HEADER_KEYS:
                    extra_headers[key_stripped] = value
            i += 1
            continue

        if lower in ("-e", "--referer"):
            referer = read_value()
            i += 1
            continue

        if lower in ("-b", "--cookie"):
            cookie = read_value()
            i += 1
            continue

        if lower in ("-a", "--user-agent"):
            user_agent = read_value()
            i += 1
            continue

        if lower in ("-i", "--url"):
            url = read_value()
            i += 1
            continue

        i += 1

    if not url:
        raise ValueError("未找到 URL，请确认粘贴的是完整 cURL")

    return CurlRequest(
        url=url,
        referer=referer,
        cookie=cookie,
        user_agent=user_agent,
        origin=origin,
        extra_headers=extra_headers,
    )


def _looks_like_curl_start(line: str) -> bool:
    """判断一行是否像新的 cURL 命令开头。"""
    return re.match(r"^\s*curl(?:\.exe)?(?:\s|$)", line, re.IGNORECASE) is not None


def _looks_like_plain_url(line: str) -> bool:
    """判断一行是否是可直接下载的 URL。"""
    return re.match(r"^\s*https?://\S+\s*$", line, re.IGNORECASE) is not None


def _split_download_inputs(raw: str) -> list[str]:
    """把多段 cURL / 多行 URL 输入切成独立任务。"""
    text = raw.replace("\r\n", "\n").strip()
    if not text:
        return []

    blocks: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            blocks.append("\n".join(current).strip())
            current.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue

        if _looks_like_curl_start(line):
            flush()
            current.append(line)
            continue

        if _looks_like_plain_url(line) and current and not _looks_like_curl_start(current[0]):
            flush()
            current.append(line)
            flush()
            continue

        if _looks_like_plain_url(line) and not current:
            current.append(line)
            flush()
            continue

        current.append(line)

    flush()
    return blocks


def parse_download_inputs(raw: str) -> list[CurlRequest]:
    """解析一个或多个 cURL / URL 下载输入。"""
    blocks = _split_download_inputs(raw)
    if not blocks:
        raise ValueError("请输入 cURL 命令或 m3u8 URL")

    requests = [parse_curl(block) for block in blocks]
    if not requests:
        raise ValueError("未找到可下载 URL")
    return requests


def to_hex(text: str) -> str:
    """生成 JDownloader forced_referer 所需的 hex 编码。"""
    return text.encode("utf-8").hex()


def build_jd_link(request: CurlRequest) -> str:
    """生成 JDownloader2 forced_referer 链接。"""
    if not request.referer:
        return request.url
    sep = "&" if "#" in request.url else "#"
    return f"{request.url}{sep}forced_referer={to_hex(request.referer)}"


def iter_download_headers(request: CurlRequest) -> list[tuple[str, str]]:
    """按 yt-dlp 需要的顺序输出请求头。"""
    headers: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(name: str, value: str) -> None:
        key = name.lower()
        if not value or key in seen:
            return
        seen.add(key)
        headers.append((name, value))

    add("User-Agent", request.user_agent)
    add("Referer", request.referer)
    add("Origin", request.origin)
    add("Cookie", request.cookie)

    for name, value in request.extra_headers.items():
        add(name, value)

    return headers
