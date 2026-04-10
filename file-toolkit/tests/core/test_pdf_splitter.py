"""PDF 分割模块单元测试"""
import pytest
from pathlib import Path

from core.pdf.splitter import split_pdf


class TestSplitPdf:
    def test_split_by_pages_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            split_pdf(
                input_file=tmp_path / "dummy.pdf",
                output_dir=tmp_path / "out",
                mode="pages",
                pages_per_file=5,
            )

    def test_split_by_range_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            split_pdf(
                input_file=tmp_path / "dummy.pdf",
                output_dir=tmp_path / "out",
                mode="range",
                page_ranges=["1-5", "6-10"],
            )

    def test_split_each_page_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            split_pdf(
                input_file=tmp_path / "dummy.pdf",
                output_dir=tmp_path / "out",
                mode="each",
            )
