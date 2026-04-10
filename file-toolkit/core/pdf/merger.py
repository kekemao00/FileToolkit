"""PDF 合并模块"""
import time
from pathlib import Path

import pypdf

from core.models import ProgressCallback, TaskResult, TaskStatus


def merge_pdf(
    input_files: list[Path],
    output_file: Path,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    PDF 合并。

    Args:
        input_files: 有序文件列表（UI 层传入用户排序结果）
        output_file: 输出文件路径（父目录不存在则自动创建）
        progress_callback: 可选进度回调 (current, total, desc)
    """
    t0 = time.time()
    try:
        if not input_files:
            return TaskResult(
                status=TaskStatus.FAILED,
                error_message="未选择任何文件",
            )

        output_file.parent.mkdir(parents=True, exist_ok=True)
        writer = pypdf.PdfWriter()
        total = len(input_files)

        for i, path in enumerate(input_files, start=1):
            reader = pypdf.PdfReader(str(path))
            for page in reader.pages:
                writer.add_page(page)
            if progress_callback:
                progress_callback(i, total, f"正在合并：{path.name} ({i}/{total})")

        with open(output_file, "wb") as f:
            writer.write(f)

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
