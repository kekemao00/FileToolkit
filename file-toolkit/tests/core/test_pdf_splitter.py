"""PDF 分割/合并/压缩模块真实集成测试"""
import io
import pytest
from pathlib import Path

import pypdf

from core.pdf.splitter import split_pdf
from core.pdf.merger import merge_pdf
from core.pdf.compressor import compress_pdf
from core.models import TaskStatus


def _make_pdf(path: Path, num_pages: int = 3) -> Path:
    """生成一个最小可用的 PDF 测试文件。"""
    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        page = pypdf.PageObject.create_blank_page(width=595, height=842)
        writer.add_page(page)
    with open(path, "wb") as f:
        writer.write(f)
    return path


class TestSplitPdf:
    def test_split_by_pages(self, tmp_path: Path) -> None:
        src = _make_pdf(tmp_path / "src.pdf", num_pages=6)
        result = split_pdf(src, tmp_path / "out", mode="pages", pages_per_file=2)
        assert result.status == TaskStatus.SUCCESS
        assert len(result.output_files) == 3
        for f in result.output_files:
            assert f.exists()

    def test_split_by_range(self, tmp_path: Path) -> None:
        src = _make_pdf(tmp_path / "src.pdf", num_pages=8)
        result = split_pdf(src, tmp_path / "out", mode="range", page_ranges=["1-3", "4-8"])
        assert result.status == TaskStatus.SUCCESS
        assert len(result.output_files) == 2
        r = pypdf.PdfReader(str(result.output_files[0]))
        assert len(r.pages) == 3

    def test_split_each_page(self, tmp_path: Path) -> None:
        src = _make_pdf(tmp_path / "src.pdf", num_pages=4)
        result = split_pdf(src, tmp_path / "out", mode="each")
        assert result.status == TaskStatus.SUCCESS
        assert len(result.output_files) == 4

    def test_split_invalid_range_returns_failed(self, tmp_path: Path) -> None:
        src = _make_pdf(tmp_path / "src.pdf", num_pages=3)
        result = split_pdf(src, tmp_path / "out", mode="range", page_ranges=["1-99"])
        assert result.status == TaskStatus.FAILED

    def test_split_progress_callback(self, tmp_path: Path) -> None:
        src = _make_pdf(tmp_path / "src.pdf", num_pages=4)
        calls: list[tuple] = []
        split_pdf(src, tmp_path / "out", mode="pages", pages_per_file=2,
                  progress_callback=lambda c, t, d: calls.append((c, t)))
        assert len(calls) == 2


class TestMergePdf:
    def test_merge_two_files(self, tmp_path: Path) -> None:
        a = _make_pdf(tmp_path / "a.pdf", 2)
        b = _make_pdf(tmp_path / "b.pdf", 3)
        out = tmp_path / "merged.pdf"
        result = merge_pdf([a, b], out)
        assert result.status == TaskStatus.SUCCESS
        assert out.exists()
        r = pypdf.PdfReader(str(out))
        assert len(r.pages) == 5

    def test_merge_empty_list_returns_failed(self, tmp_path: Path) -> None:
        result = merge_pdf([], tmp_path / "merged.pdf")
        assert result.status == TaskStatus.FAILED


class TestCompressPdf:
    def test_compress_high(self, tmp_path: Path) -> None:
        src = _make_pdf(tmp_path / "src.pdf", 2)
        out = tmp_path / "out.pdf"
        result = compress_pdf(src, out, quality="high")
        assert result.status == TaskStatus.SUCCESS
        assert out.exists()

    def test_compress_medium(self, tmp_path: Path) -> None:
        src = _make_pdf(tmp_path / "src.pdf", 2)
        out = tmp_path / "out.pdf"
        result = compress_pdf(src, out, quality="medium")
        assert result.status == TaskStatus.SUCCESS

    def test_compress_creates_output_dir(self, tmp_path: Path) -> None:
        src = _make_pdf(tmp_path / "src.pdf", 1)
        out = tmp_path / "nested" / "deep" / "out.pdf"
        result = compress_pdf(src, out, quality="high")
        assert result.status == TaskStatus.SUCCESS
        assert out.exists()
