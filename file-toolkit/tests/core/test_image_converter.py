"""图片格式转换模块单元测试"""
from pathlib import Path

import pytest

from core.image.converter import batch_convert, convert_image


class TestConvertImage:
    def test_convert_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            convert_image(
                input_file=tmp_path / "dummy.jpg",
                output_file=tmp_path / "dummy.png",
                target_format="png",
            )

    def test_batch_convert_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            batch_convert(
                input_files=[tmp_path / "a.jpg", tmp_path / "b.jpg"],
                output_dir=tmp_path / "out",
                target_format="webp",
            )
