"""
File Toolkit — 平台路径检测

检测 FFmpeg、LibreOffice 等外部二进制的可用路径。
同时兼容 flet build / PyInstaller 打包环境和开发环境，以及 Windows / macOS / Linux。
"""
import os
import shutil
import stat
import sys
from pathlib import Path

_ASSETS_BIN = Path(__file__).parent.parent / "assets" / "bin"

# macOS 从 Finder 启动的 .app 拿不到 shell 的 PATH，Homebrew 目录需要显式检查
_EXTRA_SEARCH_DIRS = [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]


def _exe_name(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def _ensure_executable(path: Path) -> None:
    """打包解压后可能丢失可执行位（Linux/macOS），尽量补上。"""
    if sys.platform == "win32" or os.access(path, os.X_OK):
        return
    try:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def _find_binary(name: str) -> Path:
    """
    查找顺序：PyInstaller 资源目录 → 应用内嵌 assets/bin（CI 打包时放入）
    → 系统 PATH → Homebrew 常见目录。都找不到时返回裸命令名，由调用方报错。
    """
    exe = _exe_name(name)
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "bin" / exe)
    candidates.append(_ASSETS_BIN / exe)

    for p in candidates:
        if p.is_file():
            _ensure_executable(p)
            return p

    found = shutil.which(exe)
    if found:
        return Path(found)

    for d in _EXTRA_SEARCH_DIRS:
        p = d / exe
        if p.is_file():
            return p

    return Path(name)


def get_ffmpeg_path() -> Path:
    """优先使用内嵌 FFmpeg，其次系统安装的版本。"""
    return _find_binary("ffmpeg")


def get_ffprobe_path() -> Path:
    """与 get_ffmpeg_path 逻辑相同，查找 ffprobe。"""
    return _find_binary("ffprobe")


def get_libreoffice_path() -> Path | None:
    """
    检测系统 LibreOffice 安装路径。
    找不到返回 None，调用方据此决定是否显示功能引导提示。
    """
    candidates = [
        Path("C:/Program Files/LibreOffice/program/soffice.exe"),
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
    ]
    for p in candidates:
        if p.exists():
            return p
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def is_libreoffice_available() -> bool:
    """简便检测：LibreOffice 是否可用。"""
    return get_libreoffice_path() is not None
