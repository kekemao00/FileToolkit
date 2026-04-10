"""PDF 压缩模块"""
from pathlib import Path
from typing import Literal

from core.models import ProgressCallback, TaskResult


def compress_pdf(
    input_file: Path,
    output_file: Path,
    quality: Literal["high", "medium", "low"] = "medium",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    PDF 压缩（通过 pikepdf 图片重采样实现）。

    Args:
        input_file: 源 PDF 路径
        output_file: 输出 PDF 路径
        quality: high（去冗余）/ medium（JPEG 75）/ low（JPEG 50，150dpi）
        progress_callback: 可选进度回调

    Returns:
        TaskResult，output_files 包含压缩后文件路径
    """
    raise NotImplementedError
