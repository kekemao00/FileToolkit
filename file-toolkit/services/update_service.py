"""
File Toolkit — 检查更新服务

从 GitHub Releases 取最新的正式版（不含预发布），与当前版本比较；
下载当前平台的安装包，用发布附带的 SHA256SUMS.txt 校验后交给 update_installer 安装。

界面通过 subscribe() 订阅状态变化：设置页切换主题时会整个重建，
状态放在这里（而不是页面里），下载中重建也不会丢进度。
"""
import asyncio
import hashlib
import platform
import re
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from core.version import app_version

REPO = "kekemao00/FileToolkit"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
SUMS_NAME = "SHA256SUMS.txt"

_CHUNK = 256 * 1024


class UpdateError(Exception):
    """可直接展示给用户的更新错误。"""


# ── 版本号 ────────────────────────────────────────────────────────────
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+.*)?$")


def parse_version(value: str) -> tuple | None:
    """"1.4.0-beta.2" → 可比较的元组；格式不对返回 None。

    按 SemVer 规则：同一版本号的预发布版低于正式版，预发布标识逐段比较（数字段低于字母段）。
    """
    m = _VERSION_RE.match(value.strip())
    if not m:
        return None
    major, minor, patch, pre = m.groups()
    core = (int(major), int(minor), int(patch or 0))
    if not pre:
        return (*core, 1, ())
    parts = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split("."))
    return (*core, 0, parts)


def is_newer(candidate: str, current: str) -> bool:
    """candidate 是否比 current 新；当前版本无法解析（开发环境读不到版本）时视为需要更新。"""
    cand = parse_version(candidate)
    if cand is None:
        return False
    cur = parse_version(current)
    return cur is None or cand > cur


# ── 平台与安装包 ──────────────────────────────────────────────────────
def platform_key(system: str | None = None, machine: str | None = None) -> str | None:
    """与发布包文件名里的平台段一致；没有对应安装包的平台返回 None。"""
    system = system or sys.platform
    machine = (machine or platform.machine()).lower()
    if system == "win32":
        # Windows on ARM 可通过系统自带的 x64 转译运行
        return "windows-x64"
    if system == "darwin":
        return "macos-arm64" if machine in ("arm64", "aarch64") else None
    if system.startswith("linux"):
        return "linux-x64" if machine in ("x86_64", "amd64") else None
    return None


def package_name(version: str, key: str) -> str:
    ext = "tar.gz" if key.startswith("linux") else "zip"
    return f"FileToolkit-{version}-{key}.{ext}"


@dataclass
class Asset:
    name: str
    url: str
    size: int = 0
    digest: str = ""  # GitHub 给出的 "sha256:…"，SHA256SUMS.txt 缺失时备用


@dataclass
class Release:
    version: str
    tag: str
    name: str
    notes: str
    html_url: str
    published_at: str
    assets: dict[str, Asset] = field(default_factory=dict)

    def package(self, key: str | None = None) -> Asset | None:
        key = key or platform_key()
        if not key:
            return None
        return self.assets.get(package_name(self.version, key))


def clean_notes(body: str) -> str:
    """去掉发布说明里固定的「下载」小节（安装包表格和手动安装说明），只留更新内容。"""
    lines = (body or "").replace("\r\n", "\n").split("\n")
    out: list[str] = []
    skipping = False
    for line in lines:
        if line.startswith("## "):
            skipping = line[3:].strip() == "下载"
            if skipping:
                continue
        if not skipping:
            out.append(line)
    text = "\n".join(out)
    # GitHub 自动生成的条目 "… by @user in https://…/pull/22" 缩成 "…（#22）"
    text = re.sub(r" by @[\w-]+ in (https://github\.com/\S+/pull/(\d+))", r"（[#\2](\1)）", text)
    text = re.sub(r"^## What's Changed\s*$", "## 更新内容", text, flags=re.M)
    text = re.sub(r"^\*\*Full Changelog\*\*: (\S+)\s*$", r"[查看完整变更](\1)", text, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_release(data: dict) -> Release:
    tag = data.get("tag_name") or ""
    assets = {
        a["name"]: Asset(
            name=a["name"],
            url=a.get("browser_download_url", ""),
            size=int(a.get("size") or 0),
            digest=a.get("digest") or "",
        )
        for a in data.get("assets", [])
        if a.get("name")
    }
    return Release(
        version=tag[1:] if tag.startswith("v") else tag,
        tag=tag,
        name=data.get("name") or tag,
        notes=clean_notes(data.get("body") or ""),
        html_url=data.get("html_url") or RELEASES_PAGE,
        published_at=(data.get("published_at") or "")[:10],
        assets=assets,
    )


def parse_sums(text: str) -> dict[str, str]:
    """sha256sum 输出 → {文件名: 小写十六进制}。兼容二进制模式的 "*文件名"。"""
    sums: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            continue
        sums[parts[1].lstrip("*").strip()] = parts[0].lower()
    return sums


# ── 网络 ─────────────────────────────────────────────────────────────
def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"FileToolkit/{app_version()}",
        },
        timeout=httpx.Timeout(20.0, read=60.0),
        follow_redirects=True,
    )


def _net_error(exc: Exception) -> UpdateError:
    if isinstance(exc, httpx.TimeoutException):
        return UpdateError("连接 GitHub 超时，请检查网络后重试")
    return UpdateError("无法连接 GitHub，请检查网络后重试")


async def fetch_latest() -> Release:
    """最新正式版（GitHub 的 releases/latest 本身就跳过预发布和草稿）。"""
    try:
        async with _client() as client:
            resp = await client.get(LATEST_API)
    except httpx.HTTPError as exc:
        raise _net_error(exc) from exc
    if resp.status_code == 404:
        raise UpdateError("还没有发布过正式版")
    if resp.status_code in (403, 429):
        raise UpdateError("GitHub 访问次数已达上限，请稍后再试")
    if resp.status_code != 200:
        raise UpdateError(f"检查更新失败（HTTP {resp.status_code}）")
    return parse_release(resp.json())


async def _expected_sha256(client: httpx.AsyncClient, release: Release, asset: Asset) -> str:
    """优先用 SHA256SUMS.txt；两处都有时必须一致，都没有则拒绝安装。"""
    from_sums = ""
    sums_asset = release.assets.get(SUMS_NAME)
    if sums_asset:
        resp = await client.get(sums_asset.url)
        if resp.status_code == 200:
            from_sums = parse_sums(resp.text).get(asset.name, "")
    from_api = asset.digest.split(":", 1)[1].lower() if asset.digest.startswith("sha256:") else ""
    if from_sums and from_api and from_sums != from_api:
        raise UpdateError("校验信息不一致，已停止更新")
    expected = from_sums or from_api
    if not expected:
        raise UpdateError("该版本缺少校验文件，已停止更新")
    return expected


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


async def download_package(
    release: Release,
    dest_dir: Path,
    on_progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> Path:
    """下载当前平台的安装包并校验 SHA256，返回校验通过的文件路径。

    已下载且校验通过的同名文件直接复用；校验失败的文件会被删除。
    """
    asset = release.package()
    if asset is None:
        raise UpdateError("这个版本没有适用于当前系统的安装包")
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / asset.name
    part = dest_dir / f"{asset.name}.part"

    try:
        async with _client() as client:
            expected = await _expected_sha256(client, release, asset)
            if target.is_file() and await asyncio.to_thread(_sha256, target) == expected:
                if on_progress:
                    on_progress(target.stat().st_size, target.stat().st_size)
                return target

            h = hashlib.sha256()
            async with client.stream("GET", asset.url) as resp:
                if resp.status_code != 200:
                    raise UpdateError(f"下载失败（HTTP {resp.status_code}）")
                total = int(resp.headers.get("content-length") or asset.size or 0)
                received = 0
                with part.open("wb") as f:
                    async for chunk in resp.aiter_bytes(_CHUNK):
                        if cancelled and cancelled():
                            raise asyncio.CancelledError
                        f.write(chunk)
                        h.update(chunk)
                        received += len(chunk)
                        if on_progress:
                            on_progress(received, total)
    except httpx.HTTPError as exc:
        part.unlink(missing_ok=True)
        raise _net_error(exc) from exc
    except BaseException:
        part.unlink(missing_ok=True)
        raise

    if h.hexdigest() != expected:
        part.unlink(missing_ok=True)
        raise UpdateError("安装包校验失败，文件可能已损坏，请重试")
    part.replace(target)
    return target


def download_dir() -> Path:
    return Path(tempfile.gettempdir()) / "FileToolkit-update"


# ── 状态（供界面订阅）────────────────────────────────────────────────
# idle / checking / latest / available / downloading / installing / ready / manual / error
@dataclass
class UpdateState:
    status: str = "idle"
    release: Release | None = None
    error: str = ""
    received: int = 0
    total: int = 0
    package: Path | None = None
    plan: object | None = None  # update_installer.InstallPlan
    checked_at: float = 0.0

    @property
    def busy(self) -> bool:
        return self.status in ("checking", "downloading", "installing")


state = UpdateState()
_listeners: list[Callable[[UpdateState], None]] = []
_cancel = False


def subscribe(listener: Callable[[UpdateState], None]) -> Callable[[], None]:
    """注册状态监听，返回取消函数。"""
    _listeners.append(listener)

    def _unsubscribe() -> None:
        if listener in _listeners:
            _listeners.remove(listener)

    return _unsubscribe


def _emit(**changes) -> None:
    for key, value in changes.items():
        setattr(state, key, value)
    for listener in list(_listeners):
        try:
            listener(state)
        except Exception:
            pass


async def check() -> UpdateState:
    """检查一次；进行中的检查 / 下载不会被打断。"""
    if state.busy:
        return state
    if state.status in ("ready", "manual") and state.release:
        # 已下载好的版本还在等重启，不再回到「发现新版本」
        return state
    _emit(status="checking", error="")
    try:
        release = await fetch_latest()
    except UpdateError as exc:
        _emit(status="error", error=str(exc), checked_at=time.time())
        return state
    if is_newer(release.version, app_version()):
        _emit(status="available", release=release, checked_at=time.time())
    else:
        _emit(status="latest", release=release, checked_at=time.time())
    return state


def cancel_download() -> None:
    global _cancel
    _cancel = True


async def download_and_prepare() -> UpdateState:
    """下载 → 校验 → 解压暂存。完成后状态为 ready（可一键重启更新）或 manual（需手动替换）。"""
    global _cancel
    release = state.release
    if release is None or state.busy:
        return state
    from services import update_installer

    _cancel = False
    _emit(status="downloading", error="", received=0, total=release.package().size if release.package() else 0)

    last = [0.0]

    def _progress(received: int, total: int) -> None:
        now = time.monotonic()
        # 进度刷新限频，避免每个分块都重绘界面
        if received < total and now - last[0] < 0.1:
            state.received, state.total = received, total
            return
        last[0] = now
        _emit(received=received, total=total)

    try:
        package = await download_package(release, download_dir(), _progress, lambda: _cancel)
    except asyncio.CancelledError:
        _emit(status="available", received=0, total=0)
        return state
    except UpdateError as exc:
        _emit(status="error", error=str(exc))
        return state
    except OSError as exc:
        _emit(status="error", error=f"保存安装包失败：{exc.strerror or exc}")
        return state

    _emit(status="installing", package=package)
    try:
        plan = await asyncio.to_thread(update_installer.prepare, package, download_dir())
    except update_installer.InstallError as exc:
        _emit(status="error", error=str(exc))
        return state
    _emit(status="ready" if plan.automatic else "manual", plan=plan)
    return state


# ── 重启前后的衔接 ────────────────────────────────────────────────────
_PENDING_KEY = "update_pending_version"


def mark_pending(version: str) -> None:
    """重启更新前记下目标版本，下次启动时据此提示结果。"""
    from services import settings_service
    settings_service.set(_PENDING_KEY, version)


def consume_pending() -> tuple[str, str] | None:
    """启动时调用一次：("updated" | "failed", 目标版本)；没有待确认的更新返回 None。"""
    from services import settings_service
    version = settings_service.get(_PENDING_KEY, "")
    if not version:
        return None
    settings_service.set(_PENDING_KEY, "")
    current = parse_version(app_version())
    target = parse_version(version)
    ok = current is not None and target is not None and current >= target
    if ok:
        # 安装包和日志都用不着了
        import shutil
        shutil.rmtree(download_dir(), ignore_errors=True)
    return ("updated" if ok else "failed"), version


def auto_check_enabled() -> bool:
    from services import settings_service
    return settings_service.get("auto_check_update", "1") == "1"
