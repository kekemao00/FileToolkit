"""最近操作

布局顺序：顶部栏（本页搜索）→ 标题区 → 统计条 → 数据表格 → 分页器 → 提示。
表格无竖线，只有行间 1px line；行高 46；悬停行变 surface-2。
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path

import flet as ft

from services import history_service
from ui import style as s
from ui.features import ACTION_LABELS
from ui.palette import c
from ui.utils import is_mounted, open_folder, show_toast

# ── 模块元数据：(icon, label) ─────────────────────────────────────────
_MODULE_META: dict[str, tuple[str, str]] = {
    "PDF":     (ft.Icons.PICTURE_AS_PDF_OUTLINED, "PDF 转换"),
    "IMAGE":   (ft.Icons.IMAGE_OUTLINED, "图片处理"),
    "MEDIA":   (ft.Icons.MOVIE_OUTLINED, "音视频"),
    "ARCHIVE": (ft.Icons.FOLDER_ZIP_OUTLINED, "压缩打包"),
    "OCR":     (ft.Icons.DOCUMENT_SCANNER_OUTLINED, "OCR 识别"),
    "AI":      (ft.Icons.AUTO_AWESOME_OUTLINED, "AI 任务"),
}

# 操作类型 -> 中文标签
_ACTION_LABELS = ACTION_LABELS

# 每页记录数
_PAGE_SIZE = 10

# 表格列宽（文件名列自适应）
_COLS = {"action": 120, "status": 96, "date": 150, "size": 72, "duration": 76, "ops": 76}


class HistoryPage(ft.Column):
    """最近操作。"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._all_tasks: list[dict] = []
        self._filtered_tasks: list[dict] = []
        self._current_page = 1
        self._search_keyword = ""

        # ── 统计数据文本 ──
        self._stat_today_value = self._make_stat_value("0")
        self._stat_today_unit = self._make_stat_unit("个文件")
        self._stat_saved_value = self._make_stat_value("—")
        self._stat_saved_unit = self._make_stat_unit("")
        self._stat_rate_value = self._make_stat_value("0")
        self._stat_rate_unit = self._make_stat_unit("%")
        self._stat_cloud_value = self._make_stat_value("—")
        self._stat_cloud_unit = self._make_stat_unit("")

        # ── 搜索框 ──
        self._search_field = s.text_field(
            hint="搜索文件名、模块或操作",
            prefix_icon=ft.Icons.SEARCH_OUTLINED,
            on_change=self._on_search_change,
            width=300,
        )

        # ── 表格主体与分页信息 ──
        self._rows_column = ft.Column(spacing=0)
        self._pagination_info = s.text(kind="small")
        self._pagination_buttons = ft.Row(spacing=4)
        self._empty_hint = ft.Container(
            content=s.empty_state(ft.Icons.HISTORY_OUTLINED, "暂无匹配的操作记录",
                                  "调整搜索关键字或完成一次文件处理后再来查看"),
            padding=ft.padding.symmetric(vertical=48),
            alignment=ft.Alignment(0, 0),
            visible=False,
        )

        # ── 组装 ──
        self._topbar = self._build_topbar()
        self.controls = [self._topbar, self._build_body()]

    # ── 生命周期 ──────────────────────────────────────────────
    def did_mount(self) -> None:
        self._reload_from_service()

    # ── 统计值文本工厂 ────────────────────────────────────────
    def _make_stat_value(self, text: str) -> ft.Text:
        return ft.Text(text, size=22, weight=ft.FontWeight.W_600, color=c("ink", "fg"), font_family=s.MONO)

    def _make_stat_unit(self, text: str) -> ft.Text:
        return s.text(text, "small")

    # ── 顶部栏 ───────────────────────────────────────────────
    def _build_topbar(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(expand=True),
                    self._search_field,
                    s.icon_button(ft.Icons.SETTINGS_OUTLINED, lambda _: self._page.go("/settings"),
                                  tooltip="设置"),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=64,
            padding=ft.padding.only(left=s.PAGE_X, right=s.PAGE_X - 4),
        )

    # ── 主体 ──────────────────────────────────────────────────
    def _build_body(self) -> ft.Control:
        return ft.Container(
            expand=True,
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self._build_header(),
                                self._build_stats(),
                                self._build_table(),
                                self._build_tip_card(),
                            ],
                            spacing=16,
                        ),
                        padding=ft.padding.only(left=s.PAGE_X, right=s.PAGE_X, top=4, bottom=24),
                    ),
                ],
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    # ── 标题区 ───────────────────────────────────────────────
    def _build_header(self) -> ft.Control:
        return ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        s.text("最近操作", "headline"),
                        s.text("管理并回顾您在过去 30 天内的所有文件处理记录。", "small"),
                    ],
                    spacing=4,
                    tight=True,
                    expand=True,
                ),
                s.button("导出记录", self._export_history, kind="secondary",
                         icon=ft.Icons.FILE_DOWNLOAD_OUTLINED, tooltip="导出为 CSV"),
                s.button("清空历史", self._confirm_clear, kind="ghost",
                         icon=ft.Icons.DELETE_OUTLINE, tooltip="清空所有历史记录"),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.END,
        )

    # ── 统计条：一张白卡片四等分 ───────────────────────────────
    def _build_stats(self) -> ft.Control:
        items = [
            ("今日处理", self._stat_today_value, self._stat_today_unit),
            ("累计处理", self._stat_saved_value, self._stat_saved_unit),
            ("成功率", self._stat_rate_value, self._stat_rate_unit),
            ("失败任务", self._stat_cloud_value, self._stat_cloud_unit),
        ]
        cells = []
        for i, (label, value, unit) in enumerate(items):
            cells.append(ft.Container(
                content=ft.Column(
                    controls=[
                        s.text(label, "caption"),
                        ft.Row(controls=[value, unit], spacing=4,
                               vertical_alignment=ft.CrossAxisAlignment.END, tight=True),
                    ],
                    spacing=6,
                    tight=True,
                ),
                padding=ft.padding.symmetric(horizontal=20, vertical=16),
                border=None if i == 0 else ft.border.only(left=ft.BorderSide(1, c("line"))),
                expand=True,
            ))
        return s.card(ft.Row(controls=cells, spacing=0), padding=0)

    # ── 数据表格 ─────────────────────────────────────────────
    def _build_table(self) -> ft.Control:
        return s.card(
            ft.Column(
                controls=[
                    self._build_table_header(),
                    self._rows_column,
                    self._empty_hint,
                    self._build_pagination(),
                ],
                spacing=0,
            ),
            padding=0,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

    def _build_table_header(self) -> ft.Control:
        def cell(text: str, width: int | None = None, expand: bool = False) -> ft.Container:
            return ft.Container(content=s.text(text, "caption"), width=width, expand=expand)

        return ft.Container(
            content=ft.Row(
                controls=[
                    cell("文件", expand=True),
                    cell("操作类型", width=_COLS["action"]),
                    cell("状态", width=_COLS["status"]),
                    cell("日期", width=_COLS["date"]),
                    cell("大小", width=_COLS["size"]),
                    cell("耗时", width=_COLS["duration"]),
                    cell("", width=_COLS["ops"]),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=40,
            padding=ft.padding.symmetric(horizontal=16),
            border=ft.border.only(bottom=ft.BorderSide(1, c("line"))),
        )

    # ── 分页器 ───────────────────────────────────────────────
    def _build_pagination(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    self._pagination_info,
                    ft.Container(expand=True),
                    self._pagination_buttons,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=52,
            padding=ft.padding.symmetric(horizontal=16),
            border=ft.border.only(top=ft.BorderSide(1, c("line"))),
        )

    # ── 提示 ─────────────────────────────────────────────────
    def _build_tip_card(self) -> ft.Control:
        return ft.Row(
            controls=[
                ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, color=c("ink-3", "fg"), size=16),
                s.text("所有处理均在本地完成，不上传任何文件。处理大文件时请确保磁盘有足够剩余空间，"
                       "失败时可重新选择文件重试。", "small", expand=True),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    # ── 数据加载与过滤 ────────────────────────────────────────
    def _reload_from_service(self) -> None:
        self._all_tasks = history_service.get_recent_tasks(limit=500)
        self._apply_filter()
        self._refresh_stats()
        if is_mounted(self._topbar):
            self.update()

    def _apply_filter(self) -> None:
        kw = self._search_keyword.strip().lower()
        if not kw:
            self._filtered_tasks = list(self._all_tasks)
        else:
            self._filtered_tasks = [
                t for t in self._all_tasks
                if kw in (t.get("input_desc") or "").lower()
                or kw in (t.get("action") or "").lower()
                or kw in (t.get("module") or "").lower()
            ]
        total_pages = max(1, (len(self._filtered_tasks) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        if self._current_page > total_pages:
            self._current_page = total_pages
        self._render_rows()
        self._render_pagination()

    def _render_rows(self) -> None:
        self._rows_column.controls.clear()
        if not self._filtered_tasks:
            self._empty_hint.visible = True
            return
        self._empty_hint.visible = False
        start = (self._current_page - 1) * _PAGE_SIZE
        end = start + _PAGE_SIZE
        for idx, task in enumerate(self._filtered_tasks[start:end]):
            self._rows_column.controls.append(
                self._build_row(task, is_last=(idx == min(_PAGE_SIZE, len(self._filtered_tasks) - start) - 1)),
            )

    def _render_pagination(self) -> None:
        total = len(self._filtered_tasks)
        start = (self._current_page - 1) * _PAGE_SIZE + (1 if total > 0 else 0)
        end = min(self._current_page * _PAGE_SIZE, total)
        self._pagination_info.value = f"显示 {start} 到 {end}，共 {total} 条记录"

        total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
        self._pagination_buttons.controls.clear()
        # 上一页
        self._pagination_buttons.controls.append(
            self._page_btn(ft.Icons.CHEVRON_LEFT_OUTLINED, None,
                           disabled=self._current_page <= 1,
                           on_click=lambda _: self._goto_page(self._current_page - 1)),
        )
        # 页码（最多 5 个，含省略号）
        for page_num in self._build_page_numbers(total_pages):
            if page_num == "...":
                self._pagination_buttons.controls.append(
                    ft.Container(
                        content=s.text("…", "small"),
                        width=30, height=30, alignment=ft.Alignment(0, 0),
                    ),
                )
            else:
                self._pagination_buttons.controls.append(
                    self._page_btn(None, str(page_num),
                                   active=(page_num == self._current_page),
                                   on_click=lambda _, p=page_num: self._goto_page(p)),
                )
        # 下一页
        self._pagination_buttons.controls.append(
            self._page_btn(ft.Icons.CHEVRON_RIGHT_OUTLINED, None,
                           disabled=self._current_page >= total_pages,
                           on_click=lambda _: self._goto_page(self._current_page + 1)),
        )

    def _build_page_numbers(self, total: int) -> list:
        """生成页码列表，含省略号。总页数 ≤ 7 时全显，否则带 ...。"""
        if total <= 7:
            return list(range(1, total + 1))
        cur = self._current_page
        pages: list = [1]
        if cur > 3:
            pages.append("...")
        for p in range(max(2, cur - 1), min(total, cur + 1) + 1):
            if p not in pages:
                pages.append(p)
        if cur < total - 2:
            pages.append("...")
        if total not in pages:
            pages.append(total)
        return pages

    def _page_btn(
        self, icon, label: str | None, *,
        active: bool = False, disabled: bool = False,
        on_click=None,
    ) -> ft.Container:
        content: ft.Control
        if icon is not None:
            content = ft.Icon(icon, color=c("ink-3" if disabled else "ink-2", "fg"), size=14)
        else:
            content = ft.Text(
                label or "", size=12, font_family=s.MONO,
                color=c("on-ink" if active else "ink-2", "fg"),
                weight=ft.FontWeight.W_500,
                text_align=ft.TextAlign.CENTER,
            )
        btn = ft.Container(
            content=content,
            width=30, height=30,
            bgcolor=c("ink") if active else None,
            border_radius=s.R_BUTTON,
            alignment=ft.Alignment(0, 0),
            on_click=None if (disabled or active) else on_click,
            opacity=0.4 if disabled else 1.0,
            animate=s.snappy(),
        )
        if not (disabled or active):
            btn.on_hover = lambda e, b=btn: self._hover_bg(b, e)
        return btn

    @staticmethod
    def _hover_bg(ctrl: ft.Container, e: ft.ControlEvent) -> None:
        ctrl.bgcolor = c("surface-2") if e.data in (True, "true") else None
        ctrl.update()

    def _goto_page(self, page_num: int) -> None:
        total_pages = max(1, (len(self._filtered_tasks) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        self._current_page = max(1, min(page_num, total_pages))
        self._render_rows()
        self._render_pagination()
        if is_mounted(self._topbar):
            self.update()

    # ── 单行 ──────────────────────────────────────────────────
    def _build_row(self, task: dict, *, is_last: bool) -> ft.Control:
        module = (task.get("module") or "").upper()
        action = task.get("action") or ""
        status = task.get("status", "success")
        input_desc = task.get("input_desc") or f"{module} · {action}"
        created_at = task.get("created_at") or ""
        duration_s = task.get("duration_s")
        output_dir = task.get("output_dir") or ""

        icon_name, module_label = _MODULE_META.get(
            module, (ft.Icons.DESCRIPTION_OUTLINED, module or "其他"),
        )
        action_label = _ACTION_LABELS.get(action, module_label)
        date_str = self._format_date(created_at)
        duration_str = "—" if status != "success" or duration_s is None else self._format_duration(duration_s)

        # 状态：圆点 + 文字（成功用强调色圆点，失败用 danger，其余中性）
        dot, text_color, status_label = {
            "success": ("accent", "ink-2", "成功"),
            "failed": ("danger", "danger", "失败"),
            "cancelled": ("ink-3", "ink-3", "已取消"),
        }.get(status, ("ink", "ink", "处理中"))

        action_buttons: list[ft.Control] = []
        if status == "success" and output_dir:
            action_buttons.append(s.icon_button(
                ft.Icons.FOLDER_OPEN_OUTLINED, lambda _, d=output_dir: self._open_dir(d),
                tooltip="打开输出目录", size=28,
            ))
        task_id = task.get("id")
        action_buttons.append(s.icon_button(
            ft.Icons.DELETE_OUTLINE, lambda _, tid=task_id: self._delete_row(tid),
            tooltip="删除此记录", size=28, color="ink-3",
        ))

        row = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(icon_name, color=c("ink-2", "fg"), size=14),
                                    width=26, height=26, bgcolor=c("surface-3"), border_radius=13,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                s.text(input_desc, "body-medium", max_lines=1,
                                       overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        expand=True,
                        padding=ft.padding.only(right=12),
                    ),
                    ft.Container(
                        content=ft.Container(
                            content=s.text(action_label, "caption", color="ink-2"),
                            height=22, alignment=ft.Alignment(0, 0),
                            border=ft.border.all(1, c("line-strong")), border_radius=11,
                            padding=ft.padding.symmetric(horizontal=8),
                        ),
                        width=_COLS["action"], alignment=ft.Alignment(-1, 0),
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(width=6, height=6, bgcolor=c(dot), border_radius=3),
                                s.text(status_label, "small", color=text_color),
                            ],
                            spacing=6, tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        width=_COLS["status"],
                    ),
                    ft.Container(content=s.text(date_str, "small"), width=_COLS["date"]),
                    # 大小列（无数据源，占位 "—"）
                    ft.Container(content=s.text("—", "mono"), width=_COLS["size"]),
                    ft.Container(content=s.text(duration_str, "mono"), width=_COLS["duration"]),
                    ft.Container(
                        content=ft.Row(controls=action_buttons, spacing=2, tight=True),
                        width=_COLS["ops"], alignment=ft.Alignment(1, 0),
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=s.H_ROW,
            padding=ft.padding.only(left=16, right=12),
            animate=s.snappy(),
        )
        row.on_hover = lambda e, r=row: self._hover_bg(r, e)
        if is_last:
            return row
        return ft.Column(
            controls=[row, ft.Container(height=1, bgcolor=c("line"), margin=ft.margin.symmetric(horizontal=12))],
            spacing=0,
        )

    # ── 统计卡数据 ────────────────────────────────────────────
    def _refresh_stats(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = sum(
            1 for t in self._all_tasks
            if (t.get("created_at") or "").startswith(today)
        )
        total = len(self._all_tasks)
        success = sum(1 for t in self._all_tasks if t.get("status") == "success")
        rate = (success / total * 100) if total > 0 else 0.0

        failed = sum(1 for t in self._all_tasks if t.get("status") == "failed")

        self._stat_today_value.value = str(today_count)
        self._stat_today_unit.value = "个文件"
        self._stat_saved_value.value = str(total)
        self._stat_saved_unit.value = "条"
        self._stat_rate_value.value = f"{rate:.1f}"
        self._stat_rate_unit.value = "%"
        self._stat_cloud_value.value = str(failed)
        self._stat_cloud_unit.value = "个"

    # ── 格式化 ────────────────────────────────────────────────
    @staticmethod
    def _format_date(created_at: str) -> str:
        """created_at 一般是 'YYYY-MM-DD HH:MM:SS'，展示友好日期。"""
        if not created_at:
            return "—"
        try:
            dt = datetime.strptime(created_at[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return created_at[:16]
        now = datetime.now()
        diff = now - dt
        if diff < timedelta(minutes=1):
            return "刚刚"
        if diff < timedelta(hours=1):
            return f"{int(diff.total_seconds() // 60)} 分钟前"
        if dt.date() == now.date():
            return f"今天 {dt.strftime('%H:%M')}"
        if dt.date() == (now - timedelta(days=1)).date():
            return f"昨天 {dt.strftime('%H:%M')}"
        return dt.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _format_duration(seconds: float | int | None) -> str:
        if seconds is None:
            return "—"
        try:
            secs = float(seconds)
        except (TypeError, ValueError):
            return "—"
        if secs < 60:
            return f"{secs:.1f}s"
        m, r = divmod(secs, 60)
        return f"{int(m)}m{int(r)}s"

    # ── 交互：搜索 / 清空 / 删除 / 打开 / 导出 ─────────────────
    def _on_search_change(self, e: ft.ControlEvent) -> None:
        self._search_keyword = (e.control.value or "")
        self._current_page = 1
        self._apply_filter()
        if is_mounted(self._topbar):
            self.update()

    def _confirm_clear(self, _) -> None:
        s.confirm(
            self._page, "清空所有历史记录？", "清空后无法恢复，已生成的文件不受影响。",
            confirm_label="清空", on_confirm=lambda: self._clear_history(None), danger=True,
        )

    def _clear_history(self, _) -> None:
        history_service.clear_history()
        show_toast(self._page, "已清空所有历史记录", kind="success")
        self._reload_from_service()

    def _delete_row(self, task_id: int | None) -> None:
        """删除单条历史记录。"""
        if task_id is None:
            return
        try:
            import sqlite3

            from services.history_service import _db_path
            if _db_path is None:
                return
            with sqlite3.connect(_db_path) as conn:
                conn.execute("DELETE FROM task_history WHERE id = ?", (task_id,))
        except sqlite3.Error as exc:
            show_toast(self._page, f"删除失败：{exc}", kind="error")
            return
        show_toast(self._page, "已删除该记录", kind="success")
        self._reload_from_service()

    def _open_dir(self, path_str: str) -> None:
        if not path_str:
            return
        if not open_folder(path_str):
            show_toast(self._page, "目录不存在或已被移动", kind="error")

    def _export_history(self, _) -> None:
        """导出当前过滤结果为 CSV。"""
        self._page.run_task(self._export_history_async)

    async def _export_history_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        picker = self._file_picker
        try:
            dir_path = await picker.get_directory_path(
                dialog_title="选择 CSV 导出目录",
            )
        except RuntimeError:
            dir_path = None
        if not dir_path:
            return
        csv_path = Path(dir_path) / f"history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "时间", "模块", "操作", "状态", "描述", "输出目录", "耗时(s)", "错误"])
                for t in self._filtered_tasks:
                    writer.writerow([
                        t.get("id", ""),
                        t.get("created_at", ""),
                        t.get("module", ""),
                        t.get("action", ""),
                        t.get("status", ""),
                        t.get("input_desc", ""),
                        t.get("output_dir", "") or "",
                        t.get("duration_s", "") or "",
                        t.get("error_msg", "") or "",
                    ])
        except OSError as exc:
            show_toast(self._page, f"导出失败：{exc}", kind="error")
            return
        show_toast(self._page, f"已导出 {len(self._filtered_tasks)} 条记录到 {csv_path.name}")
