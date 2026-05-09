"""
File Toolkit — 用户设置服务

基于 SQLite settings 表读写用户配置。
init_settings() 由 main.py 在启动时调用一次，之后 get/set 直接使用。
"""
import sqlite3
from pathlib import Path

_db_path: Path | None = None


def init_settings(db_path: Path) -> None:
    """绑定数据库路径（需在 history_service.init_db 之后调用，共享同一个 db 文件）。"""
    global _db_path
    _db_path = db_path


def get(key: str, default: str = "") -> str:
    """读取设置值，键不存在时返回 default。"""
    if _db_path is None:
        return default
    with sqlite3.connect(_db_path) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
    return row[0] if row else default


def set(key: str, value: str) -> None:
    """写入设置值（UPSERT）。"""
    if _db_path is None:
        return
    with sqlite3.connect(_db_path) as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def resolve_output_dir(input_file: Path) -> Path:
    """
    根据用户设置解析输出目录。
    设置为空时在输入文件同级创建 output/ 子目录。
    """
    user_setting = get("default_output_dir")
    if not user_setting:
        return input_file.parent / "output"
    return Path(user_setting)


def get_ai_api_key() -> str:
    """获取通用 AI API Key（兼容历史键名 openai_api_key）。

    优先顺序：ai_image_api_key（提示词出图专用） → ai_api_key → openai_api_key。
    AI 智能任务页在未配置时会用它判断是否进入引导分支。
    """
    return (
        get("ai_image_api_key", "")
        or get("ai_api_key", "")
        or get("openai_api_key", "")
    )
