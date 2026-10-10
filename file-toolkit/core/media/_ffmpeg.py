"""FFmpeg 调用：隐藏窗口、可取消、按输出时长换算进度。"""
import re
from collections.abc import Callable
from pathlib import Path

from core.platform import get_ffmpeg_path
from core.task_control import run_process

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_FFMPEG_MISSING = ("未找到 FFmpeg。Windows / Linux 安装包已内置；"
                   "源码运行或 macOS 旧版本请安装 FFmpeg（macOS：brew install ffmpeg）")


def _hms(h: str, m: str, s: str) -> float:
    return int(h) * 3600 + int(m) * 60 + float(s)


def run_ffmpeg(
    args: list[str],
    on_fraction: Callable[[float], None] | None = None,
    duration: float | None = None,
    timeout: float = 6 * 3600,
) -> None:
    """运行 `ffmpeg <args>`，失败抛 RuntimeError。

    duration 为输出时长（秒）；不传时从 FFmpeg 打印的输入时长里读取。
    """
    total = [duration or 0.0]

    def on_err(line: str) -> None:
        if not total[0] and (m := _DURATION_RE.search(line)):
            total[0] = _hms(*m.groups())

    def on_out(line: str) -> None:
        if not on_fraction or not total[0]:
            return
        key, _, value = line.partition("=")
        if key in ("out_time_us", "out_time_ms") and value.strip().isdigit():
            # 两个键的单位都是微秒（out_time_ms 是 FFmpeg 的历史命名错误）
            on_fraction(min(1.0, int(value) / 1_000_000 / total[0]))

    cmd = [str(get_ffmpeg_path()), "-hide_banner", "-nostdin", "-progress", "pipe:1", "-nostats", *args]
    try:
        code, _, err = run_process(cmd, timeout=timeout, on_stdout_line=on_out, on_stderr_line=on_err)
    except FileNotFoundError as exc:
        raise RuntimeError(_FFMPEG_MISSING) from exc
    if code != 0:
        lines = [ln for ln in err.splitlines() if ln.strip()]
        raise RuntimeError("FFmpeg 处理失败：" + ("\n".join(lines[-6:]) or f"退出码 {code}"))


class FileProgress:
    """批处理里把「第 i 个文件的完成比例」折算成整体进度回调。"""

    SCALE = 1000

    def __init__(self, files: list[Path], callback) -> None:
        self.files = files
        self.callback = callback
        self.index = 0

    def start(self, path: Path) -> Callable[[float], None]:
        self.index = self.files.index(path)
        return self.fraction

    def fraction(self, f: float) -> None:
        if self.callback:
            n = len(self.files)
            done = int((self.index + f) * self.SCALE)
            self.callback(done, n * self.SCALE, f"正在处理：{self.files[self.index].name}  {int(f * 100)}%")
