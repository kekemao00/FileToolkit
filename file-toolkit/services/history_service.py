"""
File Toolkit — 任务历史服务

基于 SQLite task_history 表记录操作历史，支持查询最近 N 条和清空。
"""
import sqlite3
from pathlib import Path

from core.models import TaskResult

_db_path: Path | None = None


def init_db(db_path: Path) -> None:
    """初始化数据库，执行 schema.sql 建表语句（幂等）。"""
    global _db_path
    _db_path = db_path
    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_path.read_text(encoding="utf-8"))


def save_task(
    module: str,
    action: str,
    result: TaskResult,
    input_desc: str,
) -> None:
    """将任务结果写入历史记录表，自动清理超出上限的旧记录。"""
    if _db_path is None:
        return

    status_str = result.status.value
    output_dir = str(result.output_dir) if result.output_dir else None

    with sqlite3.connect(_db_path) as conn:
        conn.execute(
            """INSERT INTO task_history
               (module, action, status, input_desc, output_dir, duration_s, error_msg)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                module,
                action,
                status_str,
                input_desc,
                output_dir,
                result.duration_seconds,
                result.error_message,
            ),
        )
        # 自动清理超出上限的旧记录（保留最新 N 条）
        try:
            limit = int(
                conn.execute(
                    "SELECT value FROM settings WHERE key = 'history_limit'"
                ).fetchone()[0]
            )
        except (TypeError, ValueError):
            limit = 30

        conn.execute(
            """DELETE FROM task_history WHERE id NOT IN (
               SELECT id FROM task_history ORDER BY id DESC LIMIT ?
            )""",
            (limit,),
        )


def get_recent_tasks(limit: int = 30) -> list[dict]:
    """获取最近 limit 条任务记录，按时间倒序。"""
    if _db_path is None:
        return []
    with sqlite3.connect(_db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT id, created_at, module, action, status,
                      input_desc, output_dir, duration_s, error_msg
               FROM task_history
               ORDER BY id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def clear_history() -> None:
    """清空所有历史记录。"""
    if _db_path is None:
        return
    with sqlite3.connect(_db_path) as conn:
        conn.execute("DELETE FROM task_history")
