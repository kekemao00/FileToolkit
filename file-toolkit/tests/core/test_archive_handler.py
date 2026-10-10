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


def _zip_with_raw_names(path: Path, names: dict[bytes, bytes]) -> Path:
    """写一个成员名是指定原始字节、且不带 UTF-8 标志的 ZIP（模拟 Windows 资源管理器打的包）。"""
    import zipfile

    class RawInfo(zipfile.ZipInfo):
        def _encodeFilenameFlags(self):  # noqa: N802  覆盖 zipfile 内部方法
            return self.filename.encode("cp437"), self.flag_bits

    with zipfile.ZipFile(path, "w") as zf:
        for raw, data in names.items():
            zf.writestr(RawInfo(raw.decode("cp437")), data)
    return path


class TestExtractNames:
    def test_gbk_and_utf8_names_without_flag(self, tmp_path: Path) -> None:
        src = _zip_with_raw_names(tmp_path / "win.zip", {
            "报告/年度总结.txt".encode("gbk"): b"gbk",
            "照片.txt".encode(): b"utf8",
        })
        result = extract(input_file=src, output_dir=tmp_path / "out")
        assert result.status == TaskStatus.SUCCESS
        files = {p.relative_to(tmp_path / "out").as_posix(): p.read_bytes()
                 for p in (tmp_path / "out").rglob("*") if p.is_file()}
        assert files == {"报告/年度总结.txt": b"gbk", "照片.txt": b"utf8"}

    def test_extract_many_uses_subfolders(self, tmp_path: Path) -> None:
        from core.archive.handler import extract_many

        a = compress([_make_file(tmp_path / "x.txt", "1")], tmp_path / "z1", "zip").output_files[0]
        b = compress([_make_file(tmp_path / "y.txt", "2")], tmp_path / "z2", "tar.gz").output_files[0]
        out = tmp_path / "out"
        res = extract_many([a, b], out)
        assert res.status == TaskStatus.SUCCESS
        assert (out / "x" / "x.txt").read_text() == "1"
        assert (out / "y" / "y.txt").read_text() == "2"

    def test_compress_does_not_overwrite(self, tmp_path: Path) -> None:
        f = _make_file(tmp_path / "a.txt")
        first = compress([f], tmp_path / "o", "zip").output_files[0]
        second = compress([f], tmp_path / "o", "zip").output_files[0]
        assert first != second and first.exists() and second.exists()


class TestPassword:
    def test_7z_password_roundtrip(self, tmp_path: Path) -> None:
        f = _make_file(tmp_path / "secret.txt", "s3cret")
        res = compress([f], tmp_path / "o", "7z", password="pw")
        assert res.status == TaskStatus.SUCCESS
        archive = res.output_files[0]

        assert extract(archive, tmp_path / "x").status == TaskStatus.FAILED
        wrong = extract(archive, tmp_path / "y", password="nope")
        assert wrong.status == TaskStatus.FAILED
        ok = extract(archive, tmp_path / "z", password="pw")
        assert ok.status == TaskStatus.SUCCESS
        assert (tmp_path / "z" / "secret.txt").read_text() == "s3cret"

    def test_zip_password_rejected(self, tmp_path: Path) -> None:
        f = _make_file(tmp_path / "a.txt")
        res = compress([f], tmp_path / "o", "zip", password="pw")
        assert res.status == TaskStatus.FAILED
