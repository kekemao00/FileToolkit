"""
File Toolkit — 任务控制：取消与外部进程

取消：services.task_service 在工作线程里登记一个 threading.Event，界面点「取消」时置位。
core 函数在处理每个文件前调用 check_cancelled()，外部进程（FFmpeg / LibreOffice / Tesseract）
由 run_process() 轮询并在取消时结束，任务因此真正停下，而不是在后台继续跑完。

外部进程统一走 run_process()：
  - Windows 上不弹出命令行窗口（GUI 程序启动控制台程序默认会新开一个黑窗口）
  - 输出按 UTF-8 解码并容错（FFmpeg 输出 UTF-8，中文 Windows 默认按 GBK 解码会抛异常）
"""
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable

_local = threading.local()


class TaskCancelled(Exception):  # noqa: N818  与 asyncio.CancelledError 对应
    """用户取消了任务。"""

    def __init__(self) -> None:
        super().__init__("已取消")


def set_cancel_event(event: threading.Event | None) -> None:
    """登记当前线程所属任务的取消标志（由 task_service 调用）。"""
    _local.event = event


def is_cancelled() -> bool:
    event = getattr(_local, "event", None)
    return bool(event and event.is_set())


def check_cancelled() -> None:
    if is_cancelled():
        raise TaskCancelled()


def no_window_flags() -> int:
    """Windows 下隐藏子进程控制台窗口的 creationflags，其他平台为 0。"""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def _pump(stream, sink: Callable[[str], None]) -> None:
    for raw in iter(stream.readline, b""):
        sink(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
    stream.close()


def run_process(
    cmd: list[str],
    *,
    timeout: float | None = None,
    on_stdout_line: Callable[[str], None] | None = None,
    on_stderr_line: Callable[[str], None] | None = None,
) -> tuple[int, str, str]:
    """运行外部程序直到结束，返回 (退出码, stdout, stderr 末尾)。

    取消或超时会结束进程并抛出 TaskCancelled / TimeoutError。
    stdout 全部保留（OCR 结果要用），stderr 只保留最后 200 行用于报错。
    """
    out_lines: list[str] = []
    err_tail: deque[str] = deque(maxlen=200)

    def _out(line: str) -> None:
        out_lines.append(line)
        if on_stdout_line:
            on_stdout_line(line)

    def _err(line: str) -> None:
        err_tail.append(line)
        if on_stderr_line:
            on_stderr_line(line)

    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=no_window_flags(),
    )
    readers = [
        threading.Thread(target=_pump, args=(proc.stdout, _out), daemon=True),
        threading.Thread(target=_pump, args=(proc.stderr, _err), daemon=True),
    ]
    for t in readers:
        t.start()

    deadline = time.monotonic() + timeout if timeout else None
    try:
        while proc.poll() is None:
            if is_cancelled():
                raise TaskCancelled()
            if deadline and time.monotonic() > deadline:
                raise TimeoutError(f"{_name(cmd)} 运行超时")
            time.sleep(0.1)
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    finally:
        for t in readers:
            t.join(timeout=2)
    return proc.returncode, "\n".join(out_lines), "\n".join(err_tail)


def _name(cmd: list[str]) -> str:
    from pathlib import Path
    return Path(cmd[0]).stem if cmd else "外部程序"
