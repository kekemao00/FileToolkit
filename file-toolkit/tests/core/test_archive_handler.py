"""压缩解压模块单元测试"""
from pathlib import Path

import pytest

from core.archive.handler import compress, extract


class TestCompress:
    def test_compress_zip_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            compress(
                input_paths=[tmp_path / "file.txt"],
                output_file=tmp_path / "archive.zip",
                format="zip",
            )

    def test_compress_7z_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            compress(
                input_paths=[tmp_path / "file.txt"],
                output_file=tmp_path / "archive.7z",
                format="7z",
            )


class TestExtract:
    def test_extract_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            extract(
                input_file=tmp_path / "archive.zip",
                output_dir=tmp_path / "out",
            )
