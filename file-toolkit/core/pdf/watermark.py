"""PDF 水印模块"""
import io
import time
from pathlib import Path

import pikepdf
from reportlab.pdfgen import canvas

from core.fonts import reportlab_font
from core.models import ProgressCallback, TaskResult, TaskStatus
from core.task_control import check_cancelled


def _overlay_all(pdf: pikepdf.Pdf, make_overlay,
                 progress_callback: ProgressCallback | None) -> list[pikepdf.Pdf]:
    """给每页叠加水印。同尺寸页面共用一份水印（水印 PDF 在内存里生成，不落临时文件）。

    返回的水印 Pdf 对象要一直持有到保存结束，否则叠加时复制过来的对象会失效。
    """
    cache: dict[tuple[float, float], pikepdf.Page] = {}
    keep: list[pikepdf.Pdf] = []
    total = len(pdf.pages)
    for page_num, page in enumerate(pdf.pages, start=1):
        check_cancelled()
        box = page.mediabox
        size = (round(float(box[2]) - float(box[0]), 2), round(float(box[3]) - float(box[1]), 2))
        if size not in cache:
            wm_pdf = pikepdf.open(make_overlay(*size))
            keep.append(wm_pdf)
            cache[size] = wm_pdf.pages[0]
        page.add_overlay(cache[size])
        if progress_callback:
            progress_callback(page_num, total, f"水印第 {page_num}/{total} 页")
    return keep


def add_text_watermark(
    input_file: Path,
    output_file: Path,
    text: str,
    position: str = "center",
    opacity: float = 0.3,
    font_size: int = 48,
    rotation: int = 45,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """在 PDF 每页添加文字水印。"""
    t0 = time.time()
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(0, 1, "正在添加水印...")

        with pikepdf.open(str(input_file)) as pdf:
            sources = _overlay_all(pdf, lambda w, h: _create_text_watermark(
                text, w, h, font_size, opacity, rotation, position), progress_callback)
            pdf.save(str(output_file))
            del sources

        if progress_callback:
            progress_callback(1, 1, "水印添加完成")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=[output_file],
            output_dir=output_file.parent,
            duration_seconds=time.time() - t0,
        )

    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )


def add_image_watermark(
    input_file: Path,
    output_file: Path,
    watermark_image: Path,
    position: str = "center",
    opacity: float = 0.3,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """在 PDF 每页添加图片水印。"""
    t0 = time.time()
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(0, 1, "正在添加图片水印...")

        with pikepdf.open(str(input_file)) as pdf:
            sources = _overlay_all(pdf, lambda w, h: _create_image_watermark(
                watermark_image, w, h, opacity, position), progress_callback)
            pdf.save(str(output_file))
            del sources

        if progress_callback:
            progress_callback(1, 1, "水印添加完成")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=[output_file],
            output_dir=output_file.parent,
            duration_seconds=time.time() - t0,
        )

    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )


def _create_text_watermark(
    text: str,
    page_w: float,
    page_h: float,
    font_size: int,
    opacity: float,
    rotation: int,
    position: str,
) -> io.BytesIO:
    """用 reportlab 生成单页文字水印 PDF。"""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    c.setFillAlpha(opacity)
    font = reportlab_font(text)
    c.setFont(font, font_size)

    if position == "tile":
        # 平铺模式
        text_w = c.stringWidth(text, font, font_size)
        spacing_x = text_w + 80
        spacing_y = font_size + 80
        c.saveState()
        c.rotate(rotation)
        y = -page_h
        while y < page_h * 2:
            x = -page_w
            while x < page_w * 2:
                c.drawString(x, y, text)
                x += spacing_x
            y += spacing_y
        c.restoreState()
    elif position == "center":
        c.saveState()
        c.translate(page_w / 2, page_h / 2)
        c.rotate(rotation)
        c.drawCentredString(0, 0, text)
        c.restoreState()
    else:
        # 四角定位
        margin = 30
        positions = {
            "top-left": (margin, page_h - margin - font_size),
            "top_left": (margin, page_h - margin - font_size),
            "top-right": (page_w - margin, page_h - margin - font_size),
            "top_right": (page_w - margin, page_h - margin - font_size),
            "bottom-left": (margin, margin),
            "bottom_left": (margin, margin),
            "bottom-right": (page_w - margin, margin),
            "bottom_right": (page_w - margin, margin),
        }
        x, y = positions.get(position, (page_w / 2, page_h / 2))
        c.drawString(x, y, text)

    c.save()
    buf.seek(0)
    return buf


def _create_image_watermark(
    image_path: Path,
    page_w: float,
    page_h: float,
    opacity: float,
    position: str,
) -> io.BytesIO:
    """用 reportlab 生成单页图片水印 PDF。"""
    from reportlab.lib.utils import ImageReader

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    c.setFillAlpha(opacity)

    img = ImageReader(str(image_path))
    img_w, img_h = img.getSize()

    # 缩放到页面宽度的 20%
    scale = (page_w * 0.2) / img_w
    draw_w = img_w * scale
    draw_h = img_h * scale

    margin = 30
    positions = {
        "center": ((page_w - draw_w) / 2, (page_h - draw_h) / 2),
        "top-left": (margin, page_h - draw_h - margin),
        "top_left": (margin, page_h - draw_h - margin),
        "top-right": (page_w - draw_w - margin, page_h - draw_h - margin),
        "top_right": (page_w - draw_w - margin, page_h - draw_h - margin),
        "bottom-left": (margin, margin),
        "bottom_left": (margin, margin),
        "bottom-right": (page_w - draw_w - margin, margin),
        "bottom_right": (page_w - draw_w - margin, margin),
    }
    x, y = positions.get(position, ((page_w - draw_w) / 2, (page_h - draw_h) / 2))

    c.drawImage(str(image_path), x, y, draw_w, draw_h, mask="auto")
    c.save()
    buf.seek(0)
    return buf
