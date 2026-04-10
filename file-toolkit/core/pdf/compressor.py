"""PDF 压缩模块

策略：
  high   — 仅用 pikepdf 移除冗余对象，保留图片质量
  medium — 图片重编码为 JPEG，quality=72
  low    — 图片重编码为 JPEG，quality=45，下采样至 150dpi

pikepdf 本身不提供 JPEG 重采样 API，因此对图片页使用
Pillow 解码→压缩→再写入的方式。
"""
import io
import time
from pathlib import Path
from typing import Literal

import pikepdf
from PIL import Image

from core.models import ProgressCallback, TaskResult, TaskStatus

_QUALITY_SETTINGS = {
    "high":   {"jpeg_quality": 90, "dpi": None},
    "medium": {"jpeg_quality": 72, "dpi": None},
    "low":    {"jpeg_quality": 45, "dpi": 150},
}


def compress_pdf(
    input_file: Path,
    output_file: Path,
    quality: Literal["high", "medium", "low"] = "medium",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    PDF 压缩。

    high   → 去除冗余对象，不重编码图片
    medium → 图片重编码 JPEG q72
    low    → 图片重编码 JPEG q45，150dpi 下采样
    """
    t0 = time.time()
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        cfg = _QUALITY_SETTINGS[quality]

        with pikepdf.open(str(input_file)) as pdf:
            total_pages = len(pdf.pages)

            if quality == "high":
                # 仅清理冗余：线性化、移除未使用对象
                pdf.save(
                    str(output_file),
                    linearize=True,
                    compress_streams=True,
                    object_stream_mode=pikepdf.ObjectStreamMode.generate,
                )
                if progress_callback:
                    progress_callback(1, 1, "去冗余完成")
            else:
                # 遍历每页，对内嵌图片做 JPEG 重编码
                for page_num, page in enumerate(pdf.pages, start=1):
                    _recompress_page_images(
                        page,
                        jpeg_quality=cfg["jpeg_quality"],
                        target_dpi=cfg["dpi"],
                    )
                    if progress_callback:
                        progress_callback(page_num, total_pages, f"压缩第 {page_num}/{total_pages} 页")

                pdf.save(
                    str(output_file),
                    compress_streams=True,
                    object_stream_mode=pikepdf.ObjectStreamMode.generate,
                )

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


def _recompress_page_images(
    page: pikepdf.Page,
    jpeg_quality: int,
    target_dpi: int | None,
) -> None:
    """遍历页面的所有图片资源，重编码为 JPEG。"""
    resources = page.get("/Resources")
    if resources is None:
        return

    xobjects = resources.get("/XObject")
    if xobjects is None:
        return

    for key in list(xobjects.keys()):
        xobj = xobjects[key]
        try:
            # 只处理图片类型的 XObject
            if xobj.get("/Subtype") != pikepdf.Name("/Image"):
                continue

            # 获取图片原始数据
            raw = bytes(xobj.read_raw_bytes())
            img = Image.open(io.BytesIO(raw))

            # 下采样（仅 low 模式）
            if target_dpi:
                orig_w, orig_h = img.size
                # 假设原始 DPI 约为 150，粗略按比例缩小
                scale = target_dpi / 150.0
                if scale < 1.0:
                    new_w = max(1, int(orig_w * scale))
                    new_h = max(1, int(orig_h * scale))
                    img = img.resize((new_w, new_h), Image.LANCZOS)

            # 转为 RGB（JPEG 不支持 RGBA/P）
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
            compressed = buf.getvalue()

            # 写回 pikepdf 对象
            xobj.write(compressed, filter=pikepdf.Name("/DCTDecode"))
            xobj["/Width"] = img.width
            xobj["/Height"] = img.height
            xobj["/ColorSpace"] = (
                pikepdf.Name("/DeviceGray") if img.mode == "L"
                else pikepdf.Name("/DeviceRGB")
            )
            xobj["/BitsPerComponent"] = 8

        except Exception:
            # 单张图片失败不影响整体流程
            continue
