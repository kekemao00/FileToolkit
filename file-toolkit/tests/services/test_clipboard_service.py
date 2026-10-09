"""图片复制到剪贴板：各平台命令拼装。"""
from pathlib import Path

from services import clipboard_service as cb


def test_macos_reads_file_from_env_not_argv():
    cmd = cb.build_command(Path("/tmp/中文 目录/a.png"), platform="darwin")
    assert cmd[0] == "osascript"
    assert "中文" not in cmd[2] and "FT_CLIP_IMAGE" in cmd[2]
    assert "PNGf" in cmd[2]
    assert "JPEG" in cb.build_command(Path("a.jpg"), platform="darwin")[2]


def test_linux_prefers_xclip_with_mime(monkeypatch):
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(cb.shutil, "which", lambda name: "/usr/bin/xclip" if name == "xclip" else None)
    cmd = cb.build_command(Path("/x/a.webp"), platform="linux")
    assert cmd[:5] == ["xclip", "-selection", "clipboard", "-t", "image/webp"]


def test_missing_file_is_not_copied(tmp_path: Path):
    assert cb.copy_image_file(tmp_path / "nope.png") is False
