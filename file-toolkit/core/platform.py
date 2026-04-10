"""
File Toolkit — 平台路径检测

检测 FFmpeg、LibreOffice 等外部二进制的可用路径。
同时兼容 PyInstaller 打包环境（sys._MEIPASS）和开发环境。
"""
import sys
from pathlib import Path


def get_ffmpeg_path() -> Path:
    """
    优先使用内嵌二进制，其次检测系统 PATH。
    PyInstaller 打包后资源在 sys._MEIPASS 下。
    """
    if hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "bin" / "ffmpeg.exe"
        if bundled.exists():
            return bundled

    # 开发环境：从项目 assets/bin 目录读取
    dev_path = Path(__file__).parent.parent / "assets" / "bin" / "ffmpeg.exe"
    if dev_path.exists():
        return dev_path

    # 兜底：依赖系统 PATH（要求用户自行安装）
    return Path("ffmpeg")


def get_ffprobe_path() -> Path:
    """与 get_ffmpeg_path 逻辑相同，查找 ffprobe。"""
    if hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "bin" / "ffprobe.exe"
        if bundled.exists():
            return bundled

    dev_path = Path(__file__).parent.parent / "assets" / "bin" / "ffprobe.exe"
    if dev_path.exists():
        return dev_path

    return Path("ffprobe")


def get_libreoffice_path() -> Path | None:
    """
    检测系统 LibreOffice 安装路径。
    找不到返回 None，调用方据此决定是否显示功能引导提示。
    """
    candidates = [
        Path("C:/Program Files/LibreOffice/program/soffice.exe"),
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def is_libreoffice_available() -> bool:
    """简便检测：LibreOffice 是否可用。"""
    return get_libreoffice_path() is not None
