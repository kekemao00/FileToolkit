"""
File Toolkit — 任务服务层

将 core 函数提交到线程池执行，通过回调将进度/结果推回 UI 事件循环。
大文件任务在 ThreadPoolExecutor 中运行，UI 永不卡顿。

取消：调用方取消 run_task 所在的 asyncio.Task 时，这里置位该任务的取消标志，
core 函数在下一个文件之前（外部进程则在轮询时）停下，见 core/task_control.py。
"""
import asyncio
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from core.models import ProgressCallback, TaskResult
from core.task_control import set_cancel_event

_executor = ThreadPoolExecutor(max_workers=4)


async def run_task(
    core_func: Callable,
    kwargs: dict,
    on_progress: Callable[[int, int, str], None],
    on_complete: Callable[[TaskResult], None],
) -> None:
    """
    提交 core 函数到线程池，通过回调推送进度和结果。

    调用方（UI 层）持有返回的 asyncio.Task 引用，可用于取消任务。
    core_func 必须符合 Core Engine 接口规范（接受 progress_callback 关键字参数）。
    """
    loop = asyncio.get_running_loop()
    cancel = threading.Event()
    kwargs["progress_callback"] = _make_thread_safe_callback(loop, on_progress, cancel)

    def _work() -> TaskResult:
        set_cancel_event(cancel)
        try:
            return core_func(**kwargs)
        finally:
            set_cancel_event(None)

    try:
        result: TaskResult = await loop.run_in_executor(_executor, _work)
    except asyncio.CancelledError:
        cancel.set()
        raise
    on_complete(result)


def _make_thread_safe_callback(
    loop: asyncio.AbstractEventLoop,
    callback: Callable[[int, int, str], None],
    cancel: threading.Event | None = None,
) -> ProgressCallback:
    """将回调包装为线程安全调用，从工作线程投递到事件循环；任务取消后不再推送。"""
    def wrapper(current: int, total: int, desc: str) -> None:
        if cancel is not None and cancel.is_set():
            return
        loop.call_soon_threadsafe(callback, current, total, desc)
    return wrapper
