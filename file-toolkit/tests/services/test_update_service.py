"""检查更新：版本比较、发布信息解析、下载与 SHA256 校验、状态流转。"""
import asyncio
import hashlib
from pathlib import Path

import httpx
import pytest

from services import history_service, settings_service, update_installer, update_service
from services.update_service import (
    UpdateError,
    clean_notes,
    is_newer,
    package_name,
    parse_release,
    parse_sums,
    parse_version,
    platform_key,
)

_BODY = """## 下载

| 平台 | 文件 |
|---|---|
| Windows 10/11 (x64) | `FileToolkit-1.5.0-windows-x64.zip` |

- **Windows**：解压后运行。

Windows / Linux 包内置 FFmpeg。校验和见 `SHA256SUMS.txt`。


## What's Changed
* feat: 检查更新 by @kekemao00 in https://github.com/kekemao00/FileToolkit/pull/22


**Full Changelog**: https://github.com/kekemao00/FileToolkit/compare/v1.4.1...v1.5.0"""

_PKG = b"package-bytes" * 1000
_REAL_CLIENT = httpx.AsyncClient
# 测试机所在平台（不在发布矩阵里时按 Linux 处理，同时把 platform_key 固定住）
_KEY = platform_key() or "linux-x64"


def _release_json(version: str = "1.5.0", sums: str | None = None, digest: str = "",
                  key: str = _KEY) -> dict:
    name = package_name(version, key)
    assets = [{
        "name": name,
        "browser_download_url": f"https://dl.example.com/{name}",
        "size": len(_PKG),
        "digest": digest,
    }]
    if sums is not None:
        assets.append({"name": "SHA256SUMS.txt",
                       "browser_download_url": "https://dl.example.com/SHA256SUMS.txt", "size": 1})
    return {
        "tag_name": f"v{version}",
        "name": f"File Toolkit v{version}",
        "body": _BODY,
        "html_url": f"https://github.com/kekemao00/FileToolkit/releases/tag/v{version}",
        "published_at": "2026-10-12T08:00:00Z",
        "assets": assets,
    }


@pytest.fixture
def server(monkeypatch):
    """GitHub API 与下载地址都换成本地 MockTransport。"""
    sha = hashlib.sha256(_PKG).hexdigest()
    state = {
        "latest": _release_json(sums=""),
        "latest_status": 200,
        "sums": None,
        "package": _PKG,
        "calls": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        state["calls"].append(str(request.url))
        if request.url.host == "api.github.com":
            return httpx.Response(state["latest_status"], json=state["latest"])
        if request.url.path.endswith("SHA256SUMS.txt"):
            name = state["latest"]["assets"][0]["name"]
            text = state["sums"] if state["sums"] is not None else f"{sha}  {name}\n"
            return httpx.Response(200, text=text)
        return httpx.Response(200, content=state["package"])

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _REAL_CLIENT(*args, **kwargs)

    monkeypatch.setattr(update_service.httpx, "AsyncClient", factory)
    monkeypatch.setattr(update_service, "platform_key", lambda *a: _KEY)
    monkeypatch.setattr(update_service, "app_version", lambda: "1.4.1")
    monkeypatch.setattr(update_service, "state", update_service.UpdateState())
    return state


# ── 版本 ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("newer, older", [
    ("1.4.1", "1.4.0"),
    ("v1.5.0", "1.4.9"),
    ("1.4.0", "1.4.0-beta.2"),
    ("1.4.0-beta.10", "1.4.0-beta.2"),
    ("1.4.0-rc.1", "1.4.0-beta.2"),
    ("1.4.0-beta", "1.4.0-1"),
    ("2.0", "1.99.99"),
    ("1.10.0", "1.9.0"),
])
def test_version_order(newer, older):
    assert is_newer(newer, older)
    assert not is_newer(older, newer)


def test_same_version_is_not_newer():
    assert not is_newer("v1.4.1", "1.4.1")


def test_bad_versions():
    assert parse_version("nightly") is None
    assert not is_newer("nightly", "1.0.0")
    # 读不到当前版本（"未知"）时，任何正式版都算新版本
    assert is_newer("1.0.0", "未知")


# ── 平台与发布信息 ────────────────────────────────────────────────────
def test_platform_key():
    assert platform_key("win32", "AMD64") == "windows-x64"
    assert platform_key("win32", "ARM64") == "windows-x64"
    assert platform_key("darwin", "arm64") == "macos-arm64"
    assert platform_key("darwin", "x86_64") is None
    assert platform_key("linux", "x86_64") == "linux-x64"
    assert platform_key("linux", "aarch64") is None


def test_package_name_matches_release_workflow():
    assert package_name("1.4.1", "windows-x64") == "FileToolkit-1.4.1-windows-x64.zip"
    assert package_name("1.4.1", "macos-arm64") == "FileToolkit-1.4.1-macos-arm64.zip"
    assert package_name("1.4.1", "linux-x64") == "FileToolkit-1.4.1-linux-x64.tar.gz"


def test_clean_notes_drops_download_section():
    notes = clean_notes(_BODY)
    assert notes.startswith("## What's Changed")
    assert "SHA256SUMS" not in notes and "| 平台 |" not in notes
    assert "Full Changelog" in notes


def test_parse_release():
    rel = parse_release(_release_json(key="linux-x64"))
    assert rel.version == "1.5.0" and rel.tag == "v1.5.0"
    assert rel.published_at == "2026-10-12"
    assert rel.package("linux-x64").name == "FileToolkit-1.5.0-linux-x64.tar.gz"
    assert rel.package("macos-arm64") is None


def test_parse_sums():
    a, b = "a" * 64, "B" * 64
    sums = parse_sums(f"{a}  one.zip\n{b} *two.tar.gz\nnot a line\n")
    assert sums == {"one.zip": a, "two.tar.gz": b.lower()}


# ── 网络 ─────────────────────────────────────────────────────────────
def test_check_finds_newer_release(server):
    st = asyncio.run(update_service.check())
    assert st.status == "available" and st.release.version == "1.5.0"
    assert server["calls"] == [update_service.LATEST_API]


def test_check_up_to_date(server):
    server["latest"] = _release_json("1.4.1", sums="")
    assert asyncio.run(update_service.check()).status == "latest"


def test_check_rate_limited(server):
    server["latest_status"] = 403
    st = asyncio.run(update_service.check())
    assert st.status == "error" and "上限" in st.error


def test_check_network_error(monkeypatch, server):
    def boom(request):
        raise httpx.ConnectError("offline")

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(boom)
        return _REAL_CLIENT(*args, **kwargs)

    monkeypatch.setattr(update_service.httpx, "AsyncClient", factory)
    st = asyncio.run(update_service.check())
    assert st.status == "error" and "网络" in st.error


def test_download_verifies_checksum(server, tmp_path):
    rel = parse_release(server["latest"])
    seen = []
    path = asyncio.run(update_service.download_package(rel, tmp_path, lambda r, t: seen.append((r, t))))
    assert path.read_bytes() == _PKG
    assert seen[-1] == (len(_PKG), len(_PKG))
    assert not list(tmp_path.glob("*.part"))


def test_download_rejects_bad_checksum(server, tmp_path):
    server["package"] = b"tampered"
    rel = parse_release(server["latest"])
    with pytest.raises(UpdateError, match="校验失败"):
        asyncio.run(update_service.download_package(rel, tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_download_requires_some_checksum(server, tmp_path):
    rel = parse_release(_release_json())  # 没有 SHA256SUMS.txt，也没有 digest
    with pytest.raises(UpdateError, match="缺少校验"):
        asyncio.run(update_service.download_package(rel, tmp_path))


def test_download_falls_back_to_api_digest(server, tmp_path):
    digest = "sha256:" + hashlib.sha256(_PKG).hexdigest()
    rel = parse_release(_release_json(digest=digest))
    assert asyncio.run(update_service.download_package(rel, tmp_path)).read_bytes() == _PKG


def test_download_refuses_conflicting_checksums(server, tmp_path):
    rel = parse_release(_release_json(sums="", digest="sha256:" + "0" * 64))
    with pytest.raises(UpdateError, match="不一致"):
        asyncio.run(update_service.download_package(rel, tmp_path))


def test_download_reuses_verified_file(server, tmp_path):
    rel = parse_release(server["latest"])
    asyncio.run(update_service.download_package(rel, tmp_path))
    server["calls"].clear()
    asyncio.run(update_service.download_package(rel, tmp_path))
    assert not any(u.startswith("https://dl.example.com/FileToolkit") for u in server["calls"])


def test_download_and_prepare_flow(server, tmp_path, monkeypatch):
    monkeypatch.setattr(update_service, "download_dir", lambda: tmp_path)
    plan = update_installer.InstallPlan(True, tmp_path / "pkg", tmp_path)
    monkeypatch.setattr(update_installer, "prepare", lambda package, work: plan)
    statuses = []
    unsubscribe = update_service.subscribe(lambda st: statuses.append(st.status))

    async def run():
        await update_service.check()
        return await update_service.download_and_prepare()

    st = asyncio.run(run())
    unsubscribe()
    assert st.status == "ready" and st.plan is plan
    assert statuses[0] == "checking" and "downloading" in statuses and "installing" in statuses
    # 已下载好等重启时再检查不会回到「发现新版本」
    assert asyncio.run(update_service.check()).status == "ready"


def test_cancel_download(server, tmp_path, monkeypatch):
    monkeypatch.setattr(update_service, "download_dir", lambda: tmp_path)
    monkeypatch.setattr(update_service, "_CHUNK", 1024)

    def listener(st):
        if st.status == "downloading" and st.received:
            update_service.cancel_download()

    unsubscribe = update_service.subscribe(listener)

    async def run():
        await update_service.check()
        return await update_service.download_and_prepare()

    st = asyncio.run(run())
    unsubscribe()
    assert st.status == "available"
    assert not list(tmp_path.glob("*.part")) and not list(tmp_path.glob("*.zip"))


# ── 重启前后 ─────────────────────────────────────────────────────────
def test_pending_marker(tmp_path: Path, monkeypatch):
    db = tmp_path / "app.db"
    history_service.init_db(db)
    settings_service.init_settings(db)
    monkeypatch.setattr(update_service, "app_version", lambda: "1.5.0")

    assert update_service.consume_pending() is None
    update_service.mark_pending("1.5.0")
    assert update_service.consume_pending() == ("updated", "1.5.0")
    assert update_service.consume_pending() is None
    update_service.mark_pending("1.6.0")
    assert update_service.consume_pending() == ("failed", "1.6.0")
