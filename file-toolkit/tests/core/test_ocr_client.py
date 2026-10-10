"""OCR：找不到 Tesseract 时的提示、PDF 文字提取、输出目录"""
from pathlib import Path

import pytest
from PIL import Image
from reportlab.pdfgen import canvas

from core.models import TaskStatus
from core.ocr import client
from core.ocr.client import recognize


def test_image_without_tesseract_explains_how_to_install(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(client, "find_tesseract", lambda: None)
    img = tmp_path / "a.png"
    Image.new("RGB", (10, 10), "white").save(img)
    res = recognize(img)
    assert res.status == TaskStatus.FAILED
    assert "Tesseract" in res.error_message and "brew install" in res.error_message


def test_pdf_text_goes_to_given_output_dir(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    c = canvas.Canvas(str(pdf))
    c.drawString(72, 720, "Hello OCR")
    c.save()
    res = recognize(pdf, output_dir=tmp_path / "custom")
    assert res.status == TaskStatus.SUCCESS
    assert res.output_files[0].parent == tmp_path / "custom"
    assert "Hello OCR" in res.output_files[0].read_text(encoding="utf-8")


@pytest.mark.skipif(client.find_tesseract() is None, reason="未安装 Tesseract")
def test_image_ocr_with_tesseract(tmp_path: Path) -> None:
    from PIL import ImageDraw, ImageFont

    img = Image.new("RGB", (600, 120), "white")
    ImageDraw.Draw(img).text((20, 30), "HELLO 2026", font=ImageFont.load_default(60), fill="black")
    path = tmp_path / "中文 路径.png"
    img.save(path)
    res = recognize(path, language="eng")
    assert res.status == TaskStatus.SUCCESS, res.error_message
    assert "HELLO" in res.output_files[0].read_text(encoding="utf-8")
