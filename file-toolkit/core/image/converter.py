"""图片格式转换模块"""
from pathlib import Path
from typing import Literal

from core.models import ProgressCallback, TaskResult

ImageFormat = Literal["jpg", "jpeg", "png", "webp", "heic", "bmp", "tiff"]


def convert_image(
    input_file: Path,
    output_file: Path,
    target_format: ImageFormat,
    quality: int = 95,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    图片格式转换（支持 JPG/PNG/WebP/HEIC/BMP/TIFF 互转）。

    注意：需在模块顶部调用 pillow_heif.register_heif_opener() 以支持 HEIC 格式。
    """
    raise NotImplementedError


def batch_convert(
    input_files: list[Path],
    output_dir: Path,
    target_format: ImageFormat,
    quality: int = 95,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """批量图片格式转换。"""
    raise NotImplementedError
