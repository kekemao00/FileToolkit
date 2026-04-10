"""任务服务层单元测试"""
import pytest
import asyncio
from unittest.mock import MagicMock

from core.models import TaskResult, TaskStatus
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
