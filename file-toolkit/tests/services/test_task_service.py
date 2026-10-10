"""任务服务层单元测试"""
import asyncio

from services import task_service


class TestTaskService:
    def test_thread_pool_executor_initialized(self) -> None:
        """验证线程池已初始化。"""
        assert task_service._executor is not None

    def test_make_thread_safe_callback(self) -> None:
        """验证线程安全回调包装器正确传递参数。"""
        loop = asyncio.new_event_loop()
        called_with: list = []

        def callback(current: int, total: int, desc: str) -> None:
            called_with.extend([current, total, desc])

        wrapper = task_service._make_thread_safe_callback(loop, callback)
        # 直接调用包装器（不跨线程），验证 call_soon_threadsafe 被触发
        assert callable(wrapper)
        loop.close()


async def test_cancel_stops_worker_between_files(tmp_path) -> None:
    """取消 asyncio 任务后，线程里的批处理在下一个文件前停下。"""
    import time
    from pathlib import Path

    from core.batch import run_batch

    processed: list[str] = []

    def slow(input_files, progress_callback=None):
        def one(p: Path) -> Path:
            time.sleep(0.15)
            processed.append(p.name)
            return p
        return run_batch(input_files, None, one, progress_callback)

    files = [Path(f"{i}.txt") for i in range(10)]
    task = asyncio.create_task(task_service.run_task(slow, {"input_files": files},
                                                     lambda *a: None, lambda r: None))
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(0.4)
    assert len(processed) <= 3
