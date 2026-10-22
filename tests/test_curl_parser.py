"""cURL 解析单元测试。"""

from curldownloader.curl_parser import parse_curl, parse_download_inputs

WINDOWS_CMD_CURL = r'''curl ^"https://media.example.test/videos/202605/30/sample/index.m3u8^" ^
  -H ^"accept: */*^" ^
  -H ^"referer: https://referer.example.test/^" ^
  -H ^"user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0^"'''


def test_windows_cmd_curl() -> None:
    parsed = parse_curl(WINDOWS_CMD_CURL)
    assert parsed.url.endswith("/index.m3u8")
    assert parsed.referer.endswith("/")
    print("OK")


def test_parse_multiple_plain_urls() -> None:
    parsed = parse_download_inputs(
        """https://media.example.test/one/index.m3u8
https://media.example.test/two/index.m3u8"""
    )
    assert len(parsed) == 2
    assert parsed[0].url.endswith("/one/index.m3u8")
    assert parsed[1].url.endswith("/two/index.m3u8")


def test_parse_multiple_curl_blocks() -> None:
    parsed = parse_download_inputs(
        """curl "https://media.example.test/one/index.m3u8" -H "referer: https://site.example/"

curl "https://media.example.test/two/index.m3u8" -H "user-agent: Browser"
"""
    )
    assert len(parsed) == 2
    assert parsed[0].referer == "https://site.example/"
    assert parsed[1].user_agent == "Browser"


if __name__ == "__main__":
    test_windows_cmd_curl()
    test_parse_multiple_plain_urls()
    test_parse_multiple_curl_blocks()
