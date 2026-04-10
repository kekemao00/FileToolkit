"""
File Toolkit — 任务历史服务

基于 SQLite 记录任务历史，限制条数，支持查询和再次执行。
"""
import sqlite3
from pathlib import Path

from core.models import TaskResult

_DB_PATH: Path | None = None


def init_db(db_path: Path) -> None:
    """初始化数据库，执行 schema.sql 建表语句。"""
    global _DB_PATH
    _DB_PATH = db_path
    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_path.read_text(encoding="utf-8"))


def save_task(
    module: str,
    action: str,
    result: TaskResult,
    input_desc: str,
) -> None:
    """将任务结果写入历史记录表。"""
    raise NotImplementedError


def get_recent_tasks(limit: int = 30) -> list[dict]:
    """获取最近 limit 条任务记录。"""
    raise NotImplementedError


def clear_history() -> None:
    """清空所有历史记录。"""
    raise NotImplementedError
