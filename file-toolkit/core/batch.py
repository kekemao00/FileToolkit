"""批处理骨架：逐个处理文件，单个失败不中断整批，支持取消。

process_one(path) 返回该文件的输出路径（或路径列表）；抛出的异常记为该文件的失败原因。
全部失败时任务失败，部分失败时任务成功并在 warnings 里列出失败的文件。
"""
import time
from collections.abc import Callable
from pathlib import Path

from core.models import ProgressCallback, TaskResult, TaskStatus
from core.task_control import TaskCancelled, check_cancelled


def run_batch(
    input_files: list[Path],
    output_dir: Path | None,
    process_one: Callable[[Path], Path | list[Path]],
    progress_callback: ProgressCallback | None = None,
    done_label: str = "已处理",
) -> TaskResult:
    t0 = time.time()
    if not input_files:
        return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")
    try:
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return TaskResult(status=TaskStatus.FAILED, error_message=f"无法创建输出目录：{exc}",
                          duration_seconds=time.time() - t0)

    outputs: list[Path] = []
    failures: list[str] = []
    total = len(input_files)
    for i, path in enumerate(input_files, start=1):
        try:
            check_cancelled()
            out = process_one(path)
            outputs.extend(out if isinstance(out, list) else [out])
        except TaskCancelled:
            return TaskResult(status=TaskStatus.CANCELLED, output_files=outputs, output_dir=output_dir,
                              error_message="已取消", duration_seconds=time.time() - t0)
        except Exception as exc:
            failures.append(f"{path.name}：{exc}")
        if progress_callback:
            progress_callback(i, total, f"{done_label}：{path.name} ({i}/{total})")

    if not outputs and failures:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=failures[0] if total == 1 else "全部文件处理失败：\n" + "\n".join(failures),
            output_dir=output_dir,
            duration_seconds=time.time() - t0,
        )
    return TaskResult(
        status=TaskStatus.SUCCESS,
        output_files=outputs,
        output_dir=output_dir or (outputs[0].parent if outputs else None),
        warnings=failures,
        duration_seconds=time.time() - t0,
    )
