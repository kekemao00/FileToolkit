"""图片批量重命名模块"""
from pathlib import Path

from core.models import ProgressCallback, TaskResult


def preview_rename(
    input_files: list[Path],
    template: str,
    start_index: int = 1,
) -> list[tuple[Path, str]]:
    """
    预览重命名结果（不执行实际操作）。

    Args:
        input_files: 输入文件列表
        template: 命名模板，支持占位符：
                  {n} — 序号（从 start_index 开始）
                  {n:03d} — 零填充序号
                  {date} — 文件修改日期 YYYYMMDD
                  {stem} — 原文件名（不含扩展名）
                  {ext} — 原扩展名（不含点）
        start_index: 序号起始值

    Returns:
        [(原路径, 新文件名)] 的列表
    """
    raise NotImplementedError


def batch_rename(
    input_files: list[Path],
    template: str,
    start_index: int = 1,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    批量重命名（原地重命名，不移动文件）。
    建议先调用 preview_rename 展示预览，用户确认后再执行此函数。
    """
    raise NotImplementedError
