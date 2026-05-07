"""
File Toolkit — 核心数据模型

所有跨层传递的数据结构定义于此，保持与 UI 层和 Service 层的解耦。
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Core 函数的统一返回值结构。"""
    status: TaskStatus
    output_files: list[Path] = field(default_factory=list)
    output_dir: Path | None = None
    error_message: str | None = None
    duration_seconds: float = 0.0

    @property
    def succeeded(self) -> bool:
        return self.status == TaskStatus.SUCCESS

    @property
    def failed(self) -> bool:
        return self.status == TaskStatus.FAILED


# 进度回调类型：(当前步骤, 总步骤, 描述文字)
ProgressCallback = Callable[[int, int, str], None]
