"""页面之间带文件跳转：跳转前放进来，目标页面构建时取走。"""
from pathlib import Path

_pending: list[Path] = []


def set_pending_files(paths: list[Path]) -> None:
    _pending[:] = list(paths)


def pop_pending_files() -> list[Path]:
    paths = list(_pending)
    _pending.clear()
    return paths
