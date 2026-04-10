"""PDF 分割模块"""
from pathlib import Path
from typing import Literal

from core.models import ProgressCallback, TaskResult, TaskStatus


def split_pdf(
    input_file: Path,
    output_dir: Path,
    mode: Literal["pages", "range", "each"] = "pages",
    pages_per_file: int = 5,
    page_ranges: list[str] | None = None,
    filename_template: str = "{stem}_第{n}部分",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    PDF 分割。

    Args:
        input_file: 源 PDF 路径
        output_dir: 输出目录（不存在则自动创建）
        mode: 分割模式 — pages（按页数）/ range（按范围）/ each（每页）
        pages_per_file: mode=pages 时每份页数
        page_ranges: mode=range 时页面范围列表，如 ["1-5", "6-10"]
        filename_template: 支持 {stem} {n} {start} {end} 占位符
        progress_callback: 可选进度回调 (current, total, desc)

    Returns:
        TaskResult，output_files 包含所有生成文件路径
    """
    raise NotImplementedError
