"""
File Toolkit — 安装已下载的更新

发布包是免安装的压缩包（Windows / Linux 解压即用的 FileToolkit 文件夹，macOS 的 .app），
所以「安装」就是用新文件替换当前程序所在的位置：

    prepare()  在临时目录里解压安装包，判断能否自动替换，返回 InstallPlan
    launch()   启动一个独立的小脚本：等本程序退出 → 替换文件 → 重新打开应用

运行中的程序不能覆盖自己（Windows 会锁住 exe / dll），所以替换交给退出后的脚本。
开发环境、安装目录不可写、macOS 从「下载」里直接运行（App Translocation）等情况
不自动替换，改为打开解压好的文件夹，由用户手动替换。
"""
import ctypes
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


class InstallError(Exception):
    """可直接展示给用户的安装错误。"""


@dataclass
class InstallPlan:
    automatic: bool
    package: Path
    reveal: Path                 # 手动更新时要打开的文件夹
    reason: str = ""             # 不能自动更新的原因
    source: Path | None = None   # 解压出的新程序（文件夹或 .app）
    target: Path | None = None   # 要被替换的安装位置（文件夹或 .app）
    exe: Path | None = None      # 替换后要启动的程序


# ── 定位当前安装 ──────────────────────────────────────────────────────
def current_executable() -> Path | None:
    """当前进程的可执行文件。

    flet build 打包的应用里 Python 嵌在 Flutter 宿主进程中运行，sys.executable 不可靠，
    直接问操作系统。
    """
    try:
        if sys.platform == "win32":
            buf = ctypes.create_unicode_buffer(32768)
            if ctypes.windll.kernel32.GetModuleFileNameW(None, buf, len(buf)):  # type: ignore[attr-defined]
                return Path(buf.value)
        elif sys.platform == "darwin":
            size = ctypes.c_uint32(4096)
            buf = ctypes.create_string_buffer(size.value)
            if ctypes.CDLL(None)._NSGetExecutablePath(buf, ctypes.byref(size)) == 0:
                return Path(os.path.realpath(buf.value.decode()))
        else:
            return Path(os.readlink("/proc/self/exe"))
    except (OSError, AttributeError, ValueError):
        pass
    return Path(sys.executable) if sys.executable else None


def is_packaged(exe: Path | None) -> bool:
    """flet build 打包的应用才会设置 FLET_APP_STORAGE_DATA；开发环境里宿主是 python 解释器。"""
    if exe is None or not os.environ.get("FLET_APP_STORAGE_DATA"):
        return False
    return not exe.name.lower().startswith("python")


def _writable(path: Path) -> bool:
    probe = path / ".filetoolkit-write-test"
    try:
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def locate_install(exe: Path | None, system: str | None = None) -> tuple[Path | None, str]:
    """返回 (要替换的安装位置, 不能自动更新的原因)。"""
    system = system or sys.platform
    if exe is None:
        return None, "找不到当前程序的位置"
    if system == "darwin":
        bundle = exe.parents[2] if len(exe.parents) > 2 else None
        if bundle is None or bundle.suffix != ".app":
            return None, "找不到当前应用的 .app"
        if "AppTranslocation" in bundle.parts:
            return None, "应用是从「下载」里直接打开的，macOS 不允许它替换自己"
        if not (_writable(bundle.parent) and os.access(bundle, os.W_OK)):
            return None, f"没有权限写入 {bundle.parent}"
        return bundle, ""
    root = exe.parent
    if not _writable(root):
        return None, f"没有权限写入 {root}"
    return root, ""


# ── 解压暂存 ──────────────────────────────────────────────────────────
def _single_child(folder: Path) -> Path:
    """压缩包外层包了一个 FileToolkit/ 文件夹，取它；否则就用解压目录本身。"""
    children = [p for p in folder.iterdir() if not p.name.startswith(".") and p.name != "__MACOSX"]
    return children[0] if len(children) == 1 and children[0].is_dir() else folder


def extract(package: Path, dest: Path, system: str | None = None) -> Path:
    """解压到 dest（先清空），返回新程序：Windows / Linux 为程序文件夹，macOS 为 .app。"""
    system = system or sys.platform
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    try:
        if package.name.endswith(".tar.gz"):
            with tarfile.open(package, "r:gz") as tar:
                if hasattr(tarfile, "data_filter"):
                    tar.extractall(dest, filter="data")
                else:  # pragma: no cover - Python < 3.11.4
                    tar.extractall(dest)
        elif system == "darwin" and shutil.which("ditto"):
            # ditto 保留 .app 里的符号链接和可执行位，zipfile 做不到
            subprocess.run(["ditto", "-x", "-k", str(package), str(dest)],
                           check=True, capture_output=True)
        else:
            with zipfile.ZipFile(package) as zf:
                zf.extractall(dest)
    except (OSError, tarfile.TarError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        raise InstallError(f"解压安装包失败：{exc}") from exc

    if system == "darwin":
        apps = sorted(dest.glob("*.app")) or sorted(dest.glob("*/*.app"))
        if not apps:
            raise InstallError("安装包里没有找到 .app")
        return apps[0]
    return _single_child(dest)


def _pick_exe(source: Path, current: Path, system: str) -> Path | None:
    """新程序文件夹里与当前程序同名的可执行文件；改过名时退回第一个可执行文件。"""
    if (source / current.name).is_file():
        return source / current.name
    if system == "win32":
        found = sorted(source.glob("*.exe"))
    else:
        found = sorted(p for p in source.iterdir() if p.is_file() and os.access(p, os.X_OK)
                       and not p.name.endswith(".sh"))
    return found[0] if found else None


def prepare(package: Path, work_dir: Path, exe: Path | None = None,
            system: str | None = None, packaged: bool | None = None) -> InstallPlan:
    """解压并判断能否自动替换。exe / system / packaged 仅供测试注入。"""
    system = system or sys.platform
    exe = exe if exe is not None else current_executable()
    packaged = is_packaged(exe) if packaged is None else packaged

    source = extract(package, work_dir / "staged", system)
    reveal = source.parent if system == "darwin" else source

    if not packaged:
        return InstallPlan(False, package, reveal, reason="当前是开发环境，不会自动替换程序")
    target, reason = locate_install(exe, system)
    if target is None:
        return InstallPlan(False, package, reveal, reason=reason)

    if system == "darwin":
        return InstallPlan(True, package, reveal, source=source, target=target, exe=target)
    new_exe = _pick_exe(source, exe, system)  # type: ignore[arg-type]
    if new_exe is None:
        raise InstallError("安装包里没有找到可执行文件")
    return InstallPlan(True, package, reveal, source=source, target=target,
                       exe=target / new_exe.name)


# ── 退出后替换的脚本 ──────────────────────────────────────────────────
# 脚本内容只用 ASCII（Windows 上中文脚本会因编码出错），路径一律通过命令行参数传入。
_PS1 = r"""param([int]$AppPid, [string]$Source, [string]$Target, [string]$Exe, [string]$Log)
function Write-Log($m) { Add-Content -LiteralPath $Log -Value ("{0}  {1}" -f (Get-Date -Format s), $m) -Encoding UTF8 }
$p = Get-Process -Id $AppPid -ErrorAction SilentlyContinue
if ($p) {
  if (-not $p.WaitForExit(30000)) { Stop-Process -Id $AppPid -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1 }
}
Start-Sleep -Milliseconds 500
$ok = $false
for ($i = 0; $i -lt 10 -and -not $ok; $i++) {
  & robocopy $Source $Target /E /IS /IT /R:3 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -lt 8) { $ok = $true } else { Write-Log "robocopy exit $LASTEXITCODE"; Start-Sleep -Seconds 1 }
}
if ($ok) {
  Write-Log "updated"
  Remove-Item -LiteralPath $Source -Recurse -Force -ErrorAction SilentlyContinue
} else {
  Write-Log "failed"
}
Start-Process -FilePath $Exe -WorkingDirectory (Split-Path -Parent $Exe)
"""

_SH_WAIT = r"""pid="$1"; src="$2"; target="$3"; exe="$4"; log="$5"
i=0
while kill -0 "$pid" 2>/dev/null; do
  i=$((i + 1))
  [ "$i" -eq 60 ] && kill -9 "$pid" 2>/dev/null
  [ "$i" -ge 70 ] && break
  sleep 0.5
done
sleep 0.5
"""

_SH_MACOS = _SH_WAIT + r"""backup="$target.old-update"
rm -rf "$backup"
if mv "$target" "$backup" && mv "$src" "$target"; then
  rm -rf "$backup"
  xattr -dr com.apple.quarantine "$target" 2>/dev/null
  echo updated >> "$log"
else
  [ -e "$target" ] || mv "$backup" "$target"
  echo failed >> "$log"
fi
open "$target"
"""

_SH_LINUX = _SH_WAIT + r"""if cp -a --remove-destination "$src/." "$target/"; then
  rm -rf "$src"
  echo updated >> "$log"
else
  echo failed >> "$log"
fi
cd "$target" && nohup "$exe" >/dev/null 2>&1 &
"""


def helper_script(system: str | None = None) -> tuple[str, str]:
    """(文件名, 内容)。"""
    system = system or sys.platform
    if system == "win32":
        return "apply-update.ps1", _PS1
    return "apply-update.sh", "#!/bin/sh\n" + (_SH_MACOS if system == "darwin" else _SH_LINUX)


def _clean_env() -> dict[str, str]:
    """去掉宿主注入的 FLET_* / PYTHON* 变量，免得重新打开的应用沿用本进程的配置。"""
    return {k: v for k, v in os.environ.items()
            if not k.startswith(("FLET_", "PYTHONHOME", "PYTHONPATH", "SERIOUS_PYTHON"))}


def helper_command(plan: InstallPlan, script: Path, pid: int, log: Path,
                   system: str | None = None) -> list[str]:
    system = system or sys.platform
    args = [str(plan.source), str(plan.target), str(plan.exe), str(log)]
    if system == "win32":
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden", "-File", str(script),
                "-AppPid", str(pid), "-Source", args[0], "-Target", args[1],
                "-Exe", args[2], "-Log", args[3]]
    return ["/bin/sh", str(script), str(pid), *args]


def launch(plan: InstallPlan, work_dir: Path) -> None:
    """写出并启动替换脚本（独立进程，本程序退出后它继续运行）。调用方随后应关闭应用。"""
    if not plan.automatic:
        raise InstallError(plan.reason or "当前无法自动更新")
    name, content = helper_script()
    script = work_dir / name
    log = work_dir / "update.log"
    try:
        script.write_text(content, encoding="ascii", newline="\r\n" if sys.platform == "win32" else "\n")
        cmd = helper_command(plan, script, os.getpid(), log)
        kwargs: dict = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, close_fds=True, env=_clean_env())
        if sys.platform == "win32":
            flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)  # type: ignore[attr-defined]
            try:
                # 脱离宿主的作业对象，否则宿主退出时脚本会被一起结束
                subprocess.Popen(cmd, creationflags=flags | 0x01000000, **kwargs)  # CREATE_BREAKAWAY_FROM_JOB
            except OSError:
                subprocess.Popen(cmd, creationflags=flags, **kwargs)
        else:
            subprocess.Popen(cmd, start_new_session=True, **kwargs)
    except OSError as exc:
        raise InstallError(f"启动更新程序失败：{exc}") from exc
