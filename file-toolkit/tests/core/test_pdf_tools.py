"""PDF 压缩 / 水印"""
from pathlib import Path

import numpy as np
import pikepdf
import pytest
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from core.models import TaskStatus
from core.pdf.compressor import compress_pdf
from core.pdf.watermark import add_text_watermark


@pytest.fixture
def image_pdf(tmp_path: Path) -> Path:
    """A4 三页，共用一张 2400x1600 的无损图片。"""
    rng = np.random.default_rng(0)
    arr = (rng.random((1600, 2400, 3)) * 40 + np.linspace(0, 200, 2400)[None, :, None]).astype("uint8")
    img = ImageReader(Image.fromarray(arr))
    path = tmp_path / "in.pdf"
    c = canvas.Canvas(str(path), pagesize=(595, 842))
    for _ in range(3):
        c.drawImage(img, 50, 300, 495, 330)
        c.showPage()
    c.save()
    return path


def _image_widths(path: Path) -> set[int]:
    with pikepdf.open(path) as pdf:
        return {int(x.Width) for p in pdf.pages for _, x in p.Resources.XObject.items()}


def test_compress_levels_shrink_and_downsample(image_pdf: Path, tmp_path: Path) -> None:
    sizes = {}
    for level in ("high", "medium", "low"):
        out = tmp_path / f"{level}.pdf"
        res = compress_pdf(image_pdf, out, level)
        assert res.status == TaskStatus.SUCCESS, res.error_message
        sizes[level] = out.stat().st_size
    assert sizes["low"] < sizes["medium"] < sizes["high"] <= image_pdf.stat().st_size
    # 强力：A4 长边 11.69 英寸 × 150dpi
    assert _image_widths(tmp_path / "low.pdf") == {1754}


def test_compress_keeps_original_when_not_smaller(tmp_path: Path) -> None:
    src = tmp_path / "text.pdf"
    c = canvas.Canvas(str(src))
    c.drawString(72, 720, "hello")
    c.save()
    out = tmp_path / "out.pdf"
    res = compress_pdf(src, out, "medium")
    assert res.status == TaskStatus.SUCCESS
    assert out.stat().st_size <= src.stat().st_size


def test_chinese_watermark_embeds_cjk_font(image_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "wm.pdf"
    res = add_text_watermark(image_pdf, out, "内部资料")
    assert res.status == TaskStatus.SUCCESS, res.error_message
    with pikepdf.open(out) as pdf:
        fonts = [str(f.get("/BaseFont")) for p in pdf.pages for _, x in p.Resources.XObject.items()
                 if x.get("/Subtype") == pikepdf.Name.Form
                 for _, f in x.Resources.get("/Font", {}).items()]
    # 除 reportlab 默认登记的 Helvetica 外，还要有一个能显示中文的字体
    assert any("Helvetica" not in f for f in fonts)
