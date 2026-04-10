"""图片批量压缩模块"""
from pathlib import Path
from typing import Literal

from core.models import ProgressCallback, TaskResult


def compress_images(
    input_files: list[Path],
    output_dir: Path,
    mode: Literal["quality", "size"] = "quality",
    quality: int = 80,
    target_size_kb: int | None = None,
    output_format: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    批量图片压缩。

    Args:
        input_files: 输入图片列表
        output_dir: 输出目录
        mode: quality（按质量）/ size（按目标文件大小二分法逼近，精度 ±5%）
        quality: mode=quality 时的 JPEG/WebP 质量（1-95）
        target_size_kb: mode=size 时的目标文件大小（KB）
        output_format: 输出格式，None 表示保持原格式
        progress_callback: 可选进度回调
    """
    raise NotImplementedError
