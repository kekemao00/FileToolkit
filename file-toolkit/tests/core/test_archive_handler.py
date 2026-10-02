"""压缩解压模块单元测试"""
from pathlib import Path

from core.archive.handler import compress, extract
from core.models import TaskStatus


def _make_file(path: Path, text: str = "hello") -> Path:
    path.write_text(text, encoding="utf-8")
    return path


class TestCompress:
    def test_compress_zip_roundtrip(self, tmp_path: Path) -> None:
        f1 = _make_file(tmp_path / "a.txt", "aaa")
        f2 = _make_file(tmp_path / "b.txt", "bbb")
        out_dir = tmp_path / "archive_out"

        result = compress(input_files=[f1, f2], output_dir=out_dir, format="zip")

        assert result.status == TaskStatus.SUCCESS
        archive = result.output_files[0]
        assert archive.exists() and archive.suffix == ".zip"

        # 解压回来，内容应一致
        extract_dir = tmp_path / "extracted"
        ext_result = extract(input_file=archive, output_dir=extract_dir)
        assert ext_result.status == TaskStatus.SUCCESS
        names = {p.name: p.read_text(encoding="utf-8")
                 for p in extract_dir.rglob("*") if p.is_file()}
        assert names.get("a.txt") == "aaa"
        assert names.get("b.txt") == "bbb"

    def test_empty_input_fails(self, tmp_path: Path) -> None:
        result = compress(input_files=[], output_dir=tmp_path / "out", format="zip")
        assert result.status == TaskStatus.FAILED


class TestExtract:
    def test_extract_unknown_format_fails(self, tmp_path: Path) -> None:
        bogus = _make_file(tmp_path / "not_an_archive.xyz")
        result = extract(input_file=bogus, output_dir=tmp_path / "out")
        assert result.status == TaskStatus.FAILED
