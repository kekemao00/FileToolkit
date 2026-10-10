"""PDF 压缩模块

策略：
  high   — 轻度：只做无损优化（重新压缩数据流、合并对象流、去掉未引用的资源）
  medium — 推荐：在轻度基础上，图片重编码为 JPEG q72，并限制在约 200dpi
  low    — 强力：图片重编码为 JPEG q45，限制在约 150dpi

图片用 pikepdf.PdfImage 解码（JPEG、Flate、索引色等都支持），同一张图片只处理一次
（多页共用的 Logo 不会被反复重编码而越压越糊）；重编码后没变小的图片保留原样。
图片实际显示尺寸不好算，降采样按「铺满所在页面」估算 dpi，只会偏保守、不会压过头。
"""
import io
import shutil
import time
from pathlib import Path
from typing import Literal

import pikepdf
from PIL import Image

from core.models import ProgressCallback, TaskResult, TaskStatus
from core.task_control import TaskCancelled, check_cancelled

_QUALITY_SETTINGS: dict[str, dict] = {
    "high":   {"jpeg_quality": None, "dpi": None},
    "medium": {"jpeg_quality": 72, "dpi": 200},
    "low":    {"jpeg_quality": 45, "dpi": 150},
}

_MIN_SIDE = 64  # 太小的图片（图标、线条）重编码得不偿失


def compress_pdf(
    input_file: Path,
    output_file: Path,
    quality: Literal["high", "medium", "low"] = "medium",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """PDF 压缩，见模块说明。压缩后没有变小时输出与原文件相同的内容并给出提示。"""
    t0 = time.time()
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        cfg = _QUALITY_SETTINGS[quality]

        with pikepdf.open(str(input_file)) as pdf:
            if cfg["jpeg_quality"]:
                _recompress_images(pdf, cfg["jpeg_quality"], cfg["dpi"], progress_callback)
            pdf.remove_unreferenced_resources()
            pdf.save(
                str(output_file),
                compress_streams=True,
                recompress_flate=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )

        warnings: list[str] = []
        if output_file.stat().st_size >= input_file.stat().st_size:
            shutil.copyfile(input_file, output_file)
            warnings.append(f"{input_file.name}：已经很精简，压缩后没有变小，保留了原文件内容")
        if progress_callback:
            progress_callback(1, 1, "压缩完成")
        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=[output_file],
            output_dir=output_file.parent,
            warnings=warnings,
            duration_seconds=time.time() - t0,
        )

    except TaskCancelled:
        output_file.unlink(missing_ok=True)
        return TaskResult(status=TaskStatus.CANCELLED, error_message="已取消",
                          duration_seconds=time.time() - t0)
    except pikepdf.PasswordError:
        return TaskResult(status=TaskStatus.FAILED, error_message="PDF 有打开密码，请先解除密码再压缩",
                          duration_seconds=time.time() - t0)
    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )


def _page_inches(page: pikepdf.Page) -> tuple[float, float]:
    box = page.mediabox
    return abs(float(box[2]) - float(box[0])) / 72, abs(float(box[3]) - float(box[1])) / 72


def _collect_images(pdf: pikepdf.Pdf) -> dict[tuple[int, int], tuple[pikepdf.Object, float]]:
    """所有页面（含 Form XObject 里嵌套的）图片 → (对象, 所在最大页面的长边英寸)。"""
    found: dict[tuple[int, int], tuple[pikepdf.Object, float]] = {}

    def walk(resources, page_long: float, depth: int = 0) -> None:
        if resources is None or depth > 5:
            return
        xobjects = resources.get("/XObject")
        if xobjects is None:
            return
        for _, xobj in xobjects.items():
            if not isinstance(xobj, pikepdf.Stream):
                continue
            subtype = xobj.get("/Subtype")
            if subtype == pikepdf.Name.Image:
                key = xobj.objgen
                if key == (0, 0):
                    continue
                prev = found.get(key)
                found[key] = (xobj, max(page_long, prev[1] if prev else 0))
            elif subtype == pikepdf.Name.Form:
                walk(xobj.get("/Resources"), page_long, depth + 1)

    for page in pdf.pages:
        w, h = _page_inches(page)
        walk(page.get("/Resources"), max(w, h))
    return found


def _recompress_images(pdf: pikepdf.Pdf, jpeg_quality: int, target_dpi: int | None,
                       progress_callback: ProgressCallback | None) -> None:
    images = _collect_images(pdf)
    total = max(1, len(images))
    for i, (xobj, page_long) in enumerate(images.values(), start=1):
        check_cancelled()
        try:
            _recompress_one(xobj, page_long, jpeg_quality, target_dpi)
        except Exception:
            pass  # 解不开的图片（JBIG2、特殊色彩空间等）保持原样
        if progress_callback:
            progress_callback(i, total, f"压缩图片 {i}/{total}")


def _recompress_one(xobj: pikepdf.Stream, page_long: float, jpeg_quality: int,
                    target_dpi: int | None) -> None:
    if xobj.get("/ImageMask") or int(xobj.get("/BitsPerComponent", 8)) < 8:
        return  # 黑白位图（扫描件常见）用 JPEG 反而更大
    if "/SMask" in xobj and xobj.get("/SMask") is not None and "/Decode" in xobj:
        return
    width, height = int(xobj.Width), int(xobj.Height)
    if min(width, height) < _MIN_SIDE:
        return

    img = pikepdf.PdfImage(xobj).as_pil_image()
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    if target_dpi and page_long > 0:
        max_side = int(target_dpi * page_long)
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    data = buf.getvalue()
    if len(data) >= len(xobj.read_raw_bytes()):
        return  # 没变小就不动

    xobj.write(data, filter=pikepdf.Name.DCTDecode)
    for key in ("/DecodeParms", "/Decode", "/Interpolate"):
        if key in xobj:
            del xobj[key]
    xobj.Width, xobj.Height = img.width, img.height
    xobj.ColorSpace = pikepdf.Name.DeviceGray if img.mode == "L" else pikepdf.Name.DeviceRGB
    xobj.BitsPerComponent = 8
