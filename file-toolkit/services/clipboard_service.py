"""把图片文件放进系统剪贴板（桌面端）。

Flet 0.84 的 Clipboard.set_image 只支持 Web / 移动端，桌面端在这里按平台调用系统能力：
    Windows  PowerShell + System.Windows.Forms：同时放位图和文件，
             粘到微信 / QQ / 聊天框是图片，粘到资源管理器是文件
    macOS    osascript 按 PNG / JPEG 写入
    Linux    wl-copy 或 xclip；WSL 下都没有时转给 Windows 的 powershell.exe
路径通过环境变量传给子进程，不拼进命令行，中文和空格路径都安全。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_TIMEOUT = 15

_PS_SCRIPT = (
    "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
    "$p = $env:FT_CLIP_IMAGE; "
    "$img = [System.Drawing.Image]::FromFile($p); "
    "$d = New-Object System.Windows.Forms.DataObject; "
    "$d.SetImage($img); "
    "$f = New-Object System.Collections.Specialized.StringCollection; [void]$f.Add($p); "
    "$d.SetFileDropList($f); "
    "[System.Windows.Forms.Clipboard]::SetDataObject($d, $true); "
    "$img.Dispose()"
)


def _mime(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "image/png")


def _run(cmd: list[str], env: dict | None = None, stdin: bytes | None = None) -> bool:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        res = subprocess.run(cmd, input=stdin, env=env, capture_output=True,
                             timeout=_TIMEOUT, creationflags=flags)
        return res.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _powershell(exe: str, path: str) -> bool:
    env = {**os.environ, "FT_CLIP_IMAGE": path}
    if exe.endswith("powershell.exe") and sys.platform != "win32":
        env["WSLENV"] = f"{env.get('WSLENV', '')}:FT_CLIP_IMAGE".lstrip(":")
    return _run([exe, "-NoProfile", "-NonInteractive", "-STA", "-Command", _PS_SCRIPT], env=env)


def build_command(path: Path, platform: str = sys.platform) -> list[str] | None:
    """macOS / Linux 用的命令（Windows 走 PowerShell，见 copy_image_file）；单独拆出来便于测试。"""
    if platform == "darwin":
        cls = "JPEG picture" if _mime(path) == "image/jpeg" else "«class PNGf»"
        script = f'set the clipboard to (read (POSIX file (system attribute "FT_CLIP_IMAGE")) as {cls})'
        return ["osascript", "-e", script]
    if shutil.which("wl-copy") and os.environ.get("WAYLAND_DISPLAY"):
        return ["wl-copy", "--type", _mime(path)]
    if shutil.which("xclip"):
        return ["xclip", "-selection", "clipboard", "-t", _mime(path), "-i", str(path)]
    return None


def copy_image_file(path: Path) -> bool:
    """把图片文件复制到系统剪贴板，成功返回 True。阻塞调用，界面里放到线程中执行。"""
    path = Path(path)
    if not path.is_file():
        return False
    if sys.platform == "win32":
        return _powershell("powershell", str(path))
    cmd = build_command(path)
    if cmd is not None:
        env = {**os.environ, "FT_CLIP_IMAGE": str(path)}
        stdin = path.read_bytes() if cmd[0] == "wl-copy" else None
        if _run(cmd, env=env, stdin=stdin):
            return True
    # WSL：交给 Windows 剪贴板
    ps = shutil.which("powershell.exe")
    if ps and shutil.which("wslpath"):
        try:
            win = subprocess.run(["wslpath", "-w", str(path)], capture_output=True, text=True,
                                 timeout=_TIMEOUT).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return False
        return bool(win) and _powershell(ps, win)
    return False
