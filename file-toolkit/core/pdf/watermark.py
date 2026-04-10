"""PDF 水印模块（V2 功能）"""
from pathlib import Path
from typing import Literal

from core.models import ProgressCallback, TaskResult


def add_text_watermark(
    input_file: Path,
    output_file: Path,
    text: str,
    position: Literal["center", "tile", "top-left", "top-right", "bottom-left", "bottom-right"] = "center",
    opacity: float = 0.3,
    font_size: int = 48,
    rotation: int = 45,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """在 PDF 每页添加文字水印。"""
    raise NotImplementedError


def add_image_watermark(
    input_file: Path,
    output_file: Path,
    watermark_image: Path,
    position: Literal["center", "tile", "top-left", "top-right", "bottom-left", "bottom-right"] = "center",
    opacity: float = 0.3,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """在 PDF 每页添加图片水印。"""
    raise NotImplementedError
