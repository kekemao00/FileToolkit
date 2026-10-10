"""安装更新：定位安装位置、解压暂存、替换脚本（Linux / macOS 脚本在本机真实跑一遍）。"""
import io
import os
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from pathlib import Path

import pytest

from services import update_installer
from services.update_installer import InstallError, InstallPlan

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="需要 /bin/sh")


def _tar_package(path: Path, files: dict[str, bytes], top: str = "FileToolkit") -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(data)
            info.mode = 0o755 if name == "FileToolkit" else 0o644
            tar.addfile(info, io.BytesIO(data))
    return path


def _zip_package(path: Path, files: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return path


def _fake_exe(path: Path, marker: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\necho started > '{marker}'\n")
    path.chmod(0o755)
    return path


# ── 定位 ─────────────────────────────────────────────────────────────
def test_is_packaged(monkeypatch, tmp_path):
    monkeypatch.delenv("FLET_APP_STORAGE_DATA", raising=False)
    assert not update_installer.is_packaged(tmp_path / "FileToolkit.exe")
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path))
    assert update_installer.is_packaged(tmp_path / "FileToolkit.exe")
    assert not update_installer.is_packaged(tmp_path / "python3.11")
    assert not update_installer.is_packaged(None)


def test_locate_folder_install(tmp_path):
    exe = tmp_path / "FileToolkit" / "FileToolkit.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    assert update_installer.locate_install(exe, "win32") == (exe.parent, "")


def test_locate_macos_bundle(tmp_path):
    exe = tmp_path / "File Toolkit.app" / "Contents" / "MacOS" / "File Toolkit"
    exe.parent.mkdir(parents=True)
    assert update_installer.locate_install(exe, "darwin") == (tmp_path / "File Toolkit.app", "")


def test_locate_macos_translocated(tmp_path):
    exe = tmp_path / "AppTranslocation" / "X" / "d" / "A.app" / "Contents" / "MacOS" / "A"
    exe.parent.mkdir(parents=True)
    target, reason = update_installer.locate_install(exe, "darwin")
    assert target is None and "下载" in reason


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="root 无视只读权限")
def test_locate_readonly_folder(tmp_path):
    root = tmp_path / "ro"
    root.mkdir()
    root.chmod(0o555)
    try:
        target, reason = update_installer.locate_install(root / "FileToolkit", "linux")
        assert target is None and "权限" in reason
    finally:
        root.chmod(0o755)


# ── 解压与计划 ────────────────────────────────────────────────────────
def test_prepare_dev_environment_is_manual(tmp_path):
    pkg = _tar_package(tmp_path / "p.tar.gz", {"FileToolkit": b"new"})
    plan = update_installer.prepare(pkg, tmp_path / "work", exe=tmp_path / "python3",
                                    system="linux", packaged=False)
    assert not plan.automatic and "开发环境" in plan.reason
    assert (plan.reveal / "FileToolkit").read_bytes() == b"new"


def test_prepare_windows_zip(tmp_path):
    exe = tmp_path / "app" / "FileToolkit" / "FileToolkit.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"old")
    pkg = _zip_package(tmp_path / "p.zip", {
        "FileToolkit/FileToolkit.exe": b"new",
        "FileToolkit/data/app.zip": b"app",
    })
    plan = update_installer.prepare(pkg, tmp_path / "work", exe=exe, system="win32", packaged=True)
    assert plan.automatic
    assert plan.target == exe.parent and plan.exe == exe
    assert (plan.source / "data" / "app.zip").read_bytes() == b"app"


def test_prepare_picks_renamed_exe(tmp_path):
    exe = tmp_path / "app" / "old_name.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    pkg = _zip_package(tmp_path / "p.zip", {"FileToolkit/FileToolkit.exe": b"new"})
    plan = update_installer.prepare(pkg, tmp_path / "work", exe=exe, system="win32", packaged=True)
    assert plan.exe == exe.parent / "FileToolkit.exe"


def test_prepare_rejects_package_without_exe(tmp_path):
    exe = tmp_path / "app" / "FileToolkit.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    pkg = _zip_package(tmp_path / "p.zip", {"FileToolkit/readme.txt": b"x"})
    with pytest.raises(InstallError):
        update_installer.prepare(pkg, tmp_path / "work", exe=exe, system="win32", packaged=True)


def test_bad_archive(tmp_path):
    pkg = tmp_path / "p.zip"
    pkg.write_bytes(b"not a zip")
    with pytest.raises(InstallError, match="解压"):
        update_installer.extract(pkg, tmp_path / "work", "win32")


def test_tar_cannot_escape_destination(tmp_path):
    pkg = tmp_path / "evil.tar.gz"
    with tarfile.open(pkg, "w:gz") as tar:
        info = tarfile.TarInfo("../escaped.txt")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(InstallError):
        update_installer.extract(pkg, tmp_path / "work", "linux")
    assert not (tmp_path / "escaped.txt").exists()


# ── 替换脚本 ─────────────────────────────────────────────────────────
def test_scripts_are_ascii():
    for system in ("win32", "darwin", "linux"):
        _, content = update_installer.helper_script(system)
        content.encode("ascii")


def test_windows_command_passes_paths_as_arguments(tmp_path):
    plan = InstallPlan(True, tmp_path / "p.zip", tmp_path, source=Path("C:/临时/FileToolkit"),
                       target=Path("D:/工具/FileToolkit"), exe=Path("D:/工具/FileToolkit/FileToolkit.exe"))
    cmd = update_installer.helper_command(plan, Path("C:/t/apply-update.ps1"), 1234,
                                          Path("C:/t/update.log"), "win32")
    assert cmd[0] == "powershell.exe" and "-File" in cmd
    assert cmd[cmd.index("-AppPid") + 1] == "1234"
    assert cmd[cmd.index("-Target") + 1] == str(Path("D:/工具/FileToolkit"))


def _run_helper(system: str, plan: InstallPlan, work: Path) -> Path:
    name, content = update_installer.helper_script(system)
    script = work / name
    script.write_text(content)
    log = work / "update.log"
    app = subprocess.Popen(["sleep", "0.3"])  # 模拟还在退出中的旧程序
    # 及时回收，否则僵尸进程会让脚本一直以为旧程序还在
    reaper = threading.Thread(target=app.wait)
    reaper.start()
    env = dict(os.environ)
    if system == "darwin":
        # 本机没有 macOS 的 open 命令，换成记录参数的替身
        shim = work / "bin"
        shim.mkdir(exist_ok=True)
        _fake_exe(shim / "open", work / "opened")
        env["PATH"] = f"{shim}{os.pathsep}{env['PATH']}"
    helper = subprocess.run(update_installer.helper_command(plan, script, app.pid, log, system),
                            timeout=30, capture_output=True, env=env)
    reaper.join()
    assert helper.returncode == 0, helper.stderr
    return log


@posix_only
def test_linux_helper_replaces_and_relaunches(tmp_path):
    install = tmp_path / "安装 目录" / "FileToolkit"
    marker = tmp_path / "relaunched"
    exe = _fake_exe(install / "FileToolkit", tmp_path / "old-ran")
    (install / "lib.so").write_bytes(b"old")
    (install / "user-note.txt").write_text("keep")

    new_exe = f"#!/bin/sh\necho started > '{marker}'\n".encode()
    pkg = _tar_package(tmp_path / "p.tar.gz", {"FileToolkit": new_exe, "lib.so": b"new"})
    plan = update_installer.prepare(pkg, tmp_path / "work", exe=exe, system="linux", packaged=True)
    assert plan.automatic and plan.target == install

    log = _run_helper("linux", plan, tmp_path / "work")
    assert (install / "lib.so").read_bytes() == b"new"
    assert (install / "user-note.txt").read_text() == "keep"
    assert "updated" in log.read_text()
    for _ in range(50):  # 重新打开的程序在后台运行
        if marker.exists():
            break
        time.sleep(0.1)
    assert marker.read_text().strip() == "started"


@posix_only
def test_macos_helper_swaps_bundle(tmp_path):
    bundle = tmp_path / "Applications" / "File Toolkit.app"
    (bundle / "Contents" / "MacOS").mkdir(parents=True)
    (bundle / "Contents" / "old.txt").write_text("old")
    new = tmp_path / "work" / "staged" / "File Toolkit.app"
    (new / "Contents" / "MacOS").mkdir(parents=True)
    (new / "Contents" / "new.txt").write_text("new")
    plan = InstallPlan(True, tmp_path / "p.zip", new.parent, source=new, target=bundle, exe=bundle)

    log = _run_helper("darwin", plan, tmp_path / "work")
    assert (bundle / "Contents" / "new.txt").exists()
    assert not (bundle / "Contents" / "old.txt").exists()
    assert not (tmp_path / "Applications" / "File Toolkit.app.old-update").exists()
    assert "updated" in log.read_text()
    assert (tmp_path / "work" / "opened").exists()


def test_launch_refuses_manual_plan(tmp_path):
    with pytest.raises(InstallError, match="开发环境"):
        update_installer.launch(InstallPlan(False, tmp_path, tmp_path, reason="当前是开发环境"), tmp_path)
