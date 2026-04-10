"""
File Toolkit — 用户设置服务

基于 SQLite settings 表读写用户配置，提供类型安全的 getter/setter。
"""
import sqlite3
from pathlib import Path

_DB_PATH: Path | None = None


def init_settings(db_path: Path) -> None:
    """绑定数据库路径（需在 history_service.init_db 之后调用）。"""
    global _DB_PATH
    _DB_PATH = db_path


def get(key: str, default: str = "") -> str:
    """读取设置值，键不存在时返回 default。"""
    raise NotImplementedError


def set(key: str, value: str) -> None:
    """写入设置值。"""
    raise NotImplementedError


def resolve_output_dir(input_file: Path) -> Path:
    """
    根据用户设置和输入文件路径，解析实际输出目录。
    设置为空时在输入文件同级创建 output/ 子目录。
    """
    user_setting = get("default_output_dir")
    if not user_setting:
        return input_file.parent / "output"
    return Path(user_setting)
