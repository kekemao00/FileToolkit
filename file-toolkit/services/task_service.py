"""
File Toolkit — 任务服务层

将 core 函数提交到线程池执行，通过回调将进度/结果推回 UI 事件循环。
大文件任务在 ThreadPoolExecutor 中运行，UI 永不卡顿。
"""
import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from core.models import ProgressCallback, TaskResult

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
    loop = asyncio.get_event_loop()
    kwargs["progress_callback"] = _make_thread_safe_callback(loop, on_progress)

    result: TaskResult = await loop.run_in_executor(
        _executor,
        lambda: core_func(**kwargs),
    )
    on_complete(result)


def _make_thread_safe_callback(
    loop: asyncio.AbstractEventLoop,
    callback: Callable[[int, int, str], None],
) -> ProgressCallback:
    """将回调包装为线程安全调用，从工作线程投递到事件循环。"""
    def wrapper(current: int, total: int, desc: str) -> None:
        loop.call_soon_threadsafe(callback, current, total, desc)
    return wrapper
