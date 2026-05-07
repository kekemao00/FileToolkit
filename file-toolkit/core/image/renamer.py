"""图片批量重命名模块"""
import re
import time
from datetime import date
from pathlib import Path

from core.models import ProgressCallback, TaskResult, TaskStatus


def _sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符，防止路径穿越与跨平台不兼容。"""
    # 移除路径分隔符和 Windows 非法字符
    name = re.sub(r'[/\\:*?"<>|]', "_", name)
    # 拒绝 .. 序列
    name = name.replace("..", "_")
    # 去除前后空白和点（避免 Windows 隐藏文件和尾点）
    name = name.strip(". ")
    # 空名兜底
    if not name:
        name = "unnamed"
    return name


def preview_rename(
    input_files: list[Path],
    template: str,
    start_index: int = 1,
) -> list[tuple[Path, str]]:
    """
    预览重命名结果（不执行实际操作）。

    Args:
        input_files: 输入文件列表
        template: 命名模板，支持 {name}/{n}/{n:03d}/{date}/{ext}
        start_index: 序号起始值

    Returns:
        [(原路径, 新文件名)] 的列表
    """
    today = date.today().strftime("%Y%m%d")
    results: list[tuple[Path, str]] = []

    for i, f in enumerate(input_files):
        n = start_index + i
        try:
            new_stem = template.format(
                name=f.stem, n=n, date=today, ext=f.suffix.lstrip("."),
            )
        except (KeyError, ValueError, IndexError):
            new_stem = f"{f.stem}_{n:03d}"
        new_stem = _sanitize_filename(new_stem)
        new_name = new_stem + f.suffix
        results.append((f, new_name))

    return results


def batch_rename(
    input_files: list[Path],
    template: str,
    start_number: int = 1,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    批量重命名（原地重命名，不移动文件）。

    Args:
        input_files: 输入文件列表
        template: 命名模板，支持 {name}/{n}/{n:03d}/{date}/{ext}
        start_number: 序号起始值
        progress_callback: 可选进度回调
    """
    t0 = time.time()
    try:
        if not input_files:
            return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")

        today = date.today().strftime("%Y%m%d")
        output_files: list[Path] = []
        total = len(input_files)

        for i, path in enumerate(input_files):
            n = start_number + i
            try:
                new_stem = template.format(
                    name=path.stem, n=n, date=today, ext=path.suffix.lstrip("."),
                )
            except (KeyError, ValueError, IndexError):
                new_stem = f"{path.stem}_{n:03d}"

            new_stem = _sanitize_filename(new_stem)
            new_name = new_stem + path.suffix
            new_path = path.parent / new_name

            # 冲突检测：目标文件已存在且不是自身
            if new_path.exists() and new_path != path:
                new_stem_dedup = f"{new_stem}_{n}"
                new_name = new_stem_dedup + path.suffix
                new_path = path.parent / new_name

            path.rename(new_path)
            output_files.append(new_path)

            if progress_callback:
                progress_callback(i + 1, total, f"已重命名：{path.name} → {new_name} ({i + 1}/{total})")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=output_files,
            output_dir=input_files[0].parent if input_files else None,
            duration_seconds=time.time() - t0,
        )

    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )
