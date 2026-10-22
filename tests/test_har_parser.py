"""HAR parser tests."""

from __future__ import annotations

import json
from pathlib import Path

from curldownloader.har_parser import extract_m3u8_requests_from_har, to_curl_text


def test_extract_successful_m3u8_requests(tmp_path: Path) -> None:
    har_path = tmp_path / "sample.har"
    har_path.write_text(
        json.dumps(
            {
                "log": {
                    "entries": [
                        {
                            "request": {
                                "url": "https://media.example.test/fail/index.m3u8",
                                "headers": [{"name": "Referer", "value": "https://site.example/"}],
                            },
                            "response": {"status": 0, "content": {"mimeType": "x-unknown"}},
                        },
                        {
                            "request": {
                                "url": "https://site.example/view/api/type/videojiami?url=https%3A%2F%2Fmedia.example.test%2Fencoded%2Findex.m3u8",
                                "headers": [{"name": "Referer", "value": "https://site.example/"}],
                            },
                            "response": {
                                "status": 200,
                                "content": {"mimeType": "application/json"},
                            },
                        },
                        {
                            "request": {
                                "url": "https://media.example.test/one/index.m3u8",
                                "headers": [
                                    {"name": "Referer", "value": "https://site.example/"},
                                    {"name": "User-Agent", "value": "Browser"},
                                    {"name": "Authorization", "value": "Bearer token"},
                                    {"name": "Range", "value": "bytes=0-1023"},
                                    {"name": "Accept-Encoding", "value": "gzip, deflate, br"},
                                    {"name": "If-None-Match", "value": "\"playlist-tag\""},
                                    {"name": "If-Modified-Since", "value": "Fri, 02 Oct 2026 00:00:00 GMT"},
                                ],
                            },
                            "response": {
                                "status": 200,
                                "content": {"mimeType": "application/vnd.apple.mpegurl"},
                            },
                        },
                        {
                            "request": {
                                "url": "https://media.example.test/one/index.m3u8",
                                "headers": [{"name": "Referer", "value": "https://site.example/"}],
                            },
                            "response": {
                                "status": 206,
                                "content": {"mimeType": "application/vnd.apple.mpegurl"},
                            },
                        },
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    parsed = extract_m3u8_requests_from_har(har_path)
    assert len(parsed) == 1
    assert parsed[0].url.endswith("/one/index.m3u8")
    assert parsed[0].referer == "https://site.example/"
    assert parsed[0].user_agent == "Browser"
    assert parsed[0].extra_headers["authorization"] == "Bearer token"
    assert "fail" not in to_curl_text(parsed)
    assert "videojiami" not in to_curl_text(parsed)
    assert "range:" not in to_curl_text(parsed)
    assert "accept-encoding:" not in to_curl_text(parsed)
    assert "if-none-match:" not in to_curl_text(parsed)
    assert "if-modified-since:" not in to_curl_text(parsed)


if __name__ == "__main__":
    base = Path(__file__).resolve().parent / "_test_tmp"
    base.mkdir(exist_ok=True)
    test_extract_successful_m3u8_requests(base)
    print("OK")
