"""下载器辅助逻辑测试。"""

from pathlib import Path

from curldownloader.downloader import (
    build_batch_output_names,
    find_next_numeric_output_start,
    has_file_name_conflict,
    resolve_unique_output_name,
)


def test_resolve_unique_name(tmp_path: Path) -> None:
    """验证重名时自动追加 _{序号}。"""
    (tmp_path / "video.mp4").write_bytes(b"x")
    assert resolve_unique_output_name(tmp_path, "video", resume=False) == "video_1"

    (tmp_path / "video_1.mp4").write_bytes(b"x")
    assert resolve_unique_output_name(tmp_path, "video", resume=False) == "video_2"

    assert resolve_unique_output_name(tmp_path, "other", resume=False) == "other"


def test_resume_keeps_original_name(tmp_path: Path) -> None:
    """断点续传时保留原文件名。"""
    (tmp_path / "video.mp4").write_bytes(b"done")
    (tmp_path / "video.mp4.part").write_bytes(b"partial")
    assert resolve_unique_output_name(tmp_path, "video", resume=True) == "video"


def test_find_next_numeric_output_start(tmp_path: Path) -> None:
    """只按纯数字文件名计算下一轮下载编号。"""
    assert find_next_numeric_output_start(tmp_path) == 1

    (tmp_path / "3.mp4").write_bytes(b"x")
    (tmp_path / "10.ts").write_bytes(b"x")
    (tmp_path / "video_99.mp4").write_bytes(b"x")
    (tmp_path / "abc.mp4").write_bytes(b"x")

    assert find_next_numeric_output_start(tmp_path) == 11


def test_batch_output_names_padding(tmp_path: Path) -> None:
    """编号位数随本轮最大编号补零，空目录从 1 开始。"""
    assert build_batch_output_names(tmp_path, 9) == [str(i) for i in range(1, 10)]

    names = build_batch_output_names(tmp_path, 10)
    assert names[0] == "01" and names[-1] == "10"

    names = build_batch_output_names(tmp_path, 100)
    assert names[0] == "001" and names[-1] == "100"

    names = build_batch_output_names(tmp_path, 1000)
    assert names[0] == "0001" and names[-1] == "1000"

    assert build_batch_output_names(tmp_path, 0) == []


def test_batch_output_names_continue_after_existing(tmp_path: Path) -> None:
    """已有编号时接着续号，位数按本轮最大编号补齐。"""
    (tmp_path / "9.mp4").write_bytes(b"x")
    assert build_batch_output_names(tmp_path, 3) == ["10", "11", "12"]

    (tmp_path / "012.mp4").write_bytes(b"x")
    assert find_next_numeric_output_start(tmp_path) == 13
    assert build_batch_output_names(tmp_path, 2) == ["13", "14"]


if __name__ == "__main__":
    base = Path(__file__).resolve().parent / "_test_tmp"
    base.mkdir(exist_ok=True)
    for f in base.glob("*"):
        f.unlink()
    test_resolve_unique_name(base)
    for f in base.glob("*"):
        f.unlink()
    test_resume_keeps_original_name(base)
    for f in base.glob("*"):
        f.unlink()
    test_find_next_numeric_output_start(base)
    for f in base.glob("*"):
        f.unlink()
    test_batch_output_names_padding(base)
    for f in base.glob("*"):
        f.unlink()
    test_batch_output_names_continue_after_existing(base)
    print("OK")
