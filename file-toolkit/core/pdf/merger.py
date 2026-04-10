"""PDF 合并模块"""
from pathlib import Path

from core.models import ProgressCallback, TaskResult


def merge_pdf(
    input_files: list[Path],
    output_file: Path,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    PDF 合并。

    Args:
        input_files: 有序文件列表（UI 层传入用户排序结果）
        output_file: 输出文件路径
        progress_callback: 可选进度回调 (current, total, desc)

    Returns:
        TaskResult，output_files 包含合并后的文件路径
    """
    raise NotImplementedError
