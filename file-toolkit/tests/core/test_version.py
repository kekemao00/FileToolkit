"""core.version 从 pyproject.toml 读取版本"""
import tomllib
from pathlib import Path

from core.version import app_license, app_version


def test_version_matches_pyproject():
    data = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    assert app_version() == data["project"]["version"]


def test_license_is_apache():
    assert app_license() == "Apache-2.0"
