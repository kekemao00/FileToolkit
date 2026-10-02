"""应用版本与许可证 — 运行时从 pyproject.toml 读取，避免界面上的版本号与发布版本脱节。

flet build 打包时 pyproject.toml 会随源码一起放进应用（而应用本身不是已安装的发行包，
importlib.metadata 取不到），所以直接读文件。
"""
import tomllib
from functools import cache
from pathlib import Path

_PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


@cache
def _project() -> dict:
    try:
        with _PYPROJECT.open("rb") as f:
            return tomllib.load(f).get("project", {})
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def app_version() -> str:
    """如 "1.1.0"；读取失败时返回 "未知"。"""
    return _project().get("version", "未知")


def app_license() -> str:
    """如 "Apache-2.0"。"""
    lic = _project().get("license", {})
    return lic.get("text", "") if isinstance(lic, dict) else str(lic)
