"""图片水印模块"""
from pathlib import Path
from typing import Literal

from core.models import ProgressCallback, TaskResult

Position = Literal["center", "tile", "top-left", "top-right", "bottom-left", "bottom-right"]


def add_text_watermark(
    input_files: list[Path],
    output_dir: Path,
    text: str,
    position: Position = "center",
    opacity: float = 0.3,
    font_size: int = 36,
    color: str = "#888888",
    rotation: int = 30,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """在图片上添加文字水印。"""
    raise NotImplementedError


def add_image_watermark(
    input_files: list[Path],
    output_dir: Path,
    watermark_image: Path,
    position: Position = "bottom-right",
    opacity: float = 0.5,
    scale: float = 0.2,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """在图片上叠加图片水印。"""
    raise NotImplementedError
