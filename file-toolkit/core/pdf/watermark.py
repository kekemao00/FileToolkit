"""PDF 水印模块"""
import io
import time
from pathlib import Path

import pikepdf
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from core.models import ProgressCallback, TaskResult, TaskStatus


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
            total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                # 获取页面尺寸
                mediabox = page.mediabox
                page_w = float(mediabox[2]) - float(mediabox[0])
                page_h = float(mediabox[3]) - float(mediabox[1])

                # 用 reportlab 生成水印 PDF 页
                wm_pdf = _create_text_watermark(
                    text, page_w, page_h, font_size, opacity, rotation, position,
                )

                # 叠加水印
                wm_page = pikepdf.open(wm_pdf).pages[0]
                page.add_overlay(wm_page)

                if progress_callback:
                    progress_callback(page_num, total_pages, f"水印第 {page_num}/{total_pages} 页")

            pdf.save(str(output_file))

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
            total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                mediabox = page.mediabox
                page_w = float(mediabox[2]) - float(mediabox[0])
                page_h = float(mediabox[3]) - float(mediabox[1])

                wm_pdf = _create_image_watermark(
                    watermark_image, page_w, page_h, opacity, position,
                )

                wm_page = pikepdf.open(wm_pdf).pages[0]
                page.add_overlay(wm_page)

                if progress_callback:
                    progress_callback(page_num, total_pages, f"水印第 {page_num}/{total_pages} 页")

            pdf.save(str(output_file))

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
    c.setFont("Helvetica", font_size)

    if position == "tile":
        # 平铺模式
        text_w = c.stringWidth(text, "Helvetica", font_size)
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
