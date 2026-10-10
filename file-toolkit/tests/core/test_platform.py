"""core.platform 外部二进制查找"""
import stat
import sys

import pytest

from core import platform as plat


@pytest.fixture
def fake_bin(tmp_path, monkeypatch):
    monkeypatch.setattr(plat, "_ASSETS_BIN", tmp_path)
    monkeypatch.setattr(plat, "_EXTRA_SEARCH_DIRS", [])
    monkeypatch.setattr(plat.shutil, "which", lambda _name: None)
    return tmp_path


def test_prefers_bundled_binary(fake_bin):
    exe = fake_bin / plat._exe_name("ffmpeg")
    exe.write_bytes(b"")
    assert plat.get_ffmpeg_path() == exe


@pytest.mark.skipif(sys.platform == "win32", reason="可执行位仅适用于类 Unix")
def test_restores_executable_bit(fake_bin):
    exe = fake_bin / "ffmpeg"
    exe.write_bytes(b"")
    exe.chmod(0o644)
    plat.get_ffmpeg_path()
    assert exe.stat().st_mode & stat.S_IXUSR


def test_falls_back_to_system_path(fake_bin, monkeypatch):
    monkeypatch.setattr(plat.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert plat.get_ffmpeg_path().name == plat._exe_name("ffmpeg")
    assert plat.get_ffmpeg_path().parent == plat.Path("/usr/bin")


def test_returns_bare_name_when_missing(fake_bin):
    assert plat.get_ffprobe_path() == plat.Path("ffprobe")
