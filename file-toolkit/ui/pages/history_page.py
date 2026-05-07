"""最近操作 — Figma 1:1 还原

严格遵循 Figma 设计稿的色值、字体、间距、圆角、尺寸。
布局顺序：顶部栏 → 标题区 → Dashboard 统计卡片 → 数据表格 → 分页器 → 效率提示卡片。
"""
import csv
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import flet as ft

from services import history_service
from ui.utils import show_toast

# ── 模块元数据：(icon_bg, icon_color, icon, label) ────────────────────
_MODULE_META: dict[str, tuple[str, str, str, str]] = {
    "PDF":     (ft.Colors.with_opacity(0.1, "#fb5151"), "#b31b25", ft.Icons.PICTURE_AS_PDF, "PDF 转换"),
    "IMAGE":   (ft.Colors.with_opacity(0.1, "#2aa7ff"), "#005f98", ft.Icons.IMAGE, "图片处理"),
    "MEDIA":   (ft.Colors.with_opacity(0.1, "#d9caff"), "#6b1ef3", ft.Icons.MOVIE, "音视频"),
    "ARCHIVE": ("#d5e3ff", "#162f50", ft.Icons.FOLDER_ZIP, "压缩打包"),
    "OCR":     ("#cffafe", "#0891b2", ft.Icons.DOCUMENT_SCANNER, "OCR 识别"),
    "AI":      ("#ede9fe", "#7c3aed", ft.Icons.AUTO_AWESOME, "AI 任务"),
}

# 操作类型 -> 中文标签
_ACTION_LABELS: dict[str, str] = {
    "merge": "合并", "split": "拆分", "compress": "压缩",
    "convert": "格式转换", "watermark": "加水印", "rename": "批量重命名",
    "extract": "提取", "audio_convert": "音频转换", "audio_extract": "音频提取",
    "video_convert": "视频转换", "video_compress": "视频压缩", "video_cut": "视频剪辑",
    "archive": "打包", "extract_archive": "解压",
    "ocr": "OCR 识别",
    "ai_task": "AI 处理",
}

# 每页记录数
_PAGE_SIZE = 10


class HistoryPage(ft.Column):
    """最近操作 — Figma 1:1 还原。"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._all_tasks: list[dict] = []
        self._filtered_tasks: list[dict] = []
        self._current_page = 1
        self._search_keyword = ""

        # ── 统计卡片数据文本 ──
        self._stat_today_value = self._make_stat_value("0", "#00253f")
        self._stat_today_unit = self._make_stat_unit("个文件", "#00253f")
        self._stat_saved_value = self._make_stat_value("—", "#5500cd")
        self._stat_saved_unit = self._make_stat_unit("", "#5500cd")
        self._stat_rate_value = self._make_stat_value("0", "#004d57")
        self._stat_rate_unit = self._make_stat_unit("%", "#004d57")
        self._stat_cloud_value = self._make_stat_value("—", "#162f50")
        self._stat_cloud_unit = self._make_stat_unit("", "#162f50")

        # ── 搜索框 ──
        self._search_field = ft.TextField(
            hint_text="搜索功能或指令...",
            hint_style=ft.TextStyle(
                size=13, color="#94a3b8",
                font_family="42dot Sans", weight=ft.FontWeight.W_500,
            ),
            text_size=13,
            text_style=ft.TextStyle(color="#162f50", font_family="42dot Sans"),
            border=ft.InputBorder.NONE,
            content_padding=ft.padding.symmetric(horizontal=0, vertical=0),
            cursor_color="#005f98",
            on_change=self._on_search_change,
            expand=True,
        )

        # ── 表格主体与分页信息 ──
        self._rows_column = ft.Column(spacing=0)
        self._pagination_info = ft.Text(
            "", size=12, color="#455c7f",
            font_family="Plus Jakarta Sans", weight=ft.FontWeight.W_500,
        )
        self._pagination_buttons = ft.Row(spacing=4)
        self._empty_hint = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.HISTORY, size=48, color="#94a3b8"),
                    ft.Text("暂无匹配的操作记录", color="#455c7f", size=14,
                            font_family="42dot Sans"),
                    ft.Text("调整搜索关键字或完成一次文件处理后再来查看",
                            color="#94a3b8", size=12, font_family="42dot Sans"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.padding.symmetric(vertical=64),
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
    def _make_stat_value(self, text: str, color: str) -> ft.Text:
        return ft.Text(
            text, size=24, weight=ft.FontWeight.W_900,
            color=color, font_family="Plus Jakarta Sans",
        )

    def _make_stat_unit(self, text: str, color: str) -> ft.Text:
        return ft.Text(
            text, size=14, weight=ft.FontWeight.W_500,
            color=color, font_family="42dot Sans",
        )

    # ── 顶部栏（高 80px）──────────────────────────────────────
    def _build_topbar(self) -> ft.Control:
        search_box = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SEARCH, color="#94a3b8", size=15),
                    self._search_field,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=360, height=42,
            bgcolor=ft.Colors.with_opacity(0.5, "#f8fafc"),
            border=ft.border.all(1, ft.Colors.with_opacity(0.6, "#e2e8f0")),
            border_radius=9999,
            padding=ft.padding.symmetric(horizontal=16),
        )
        circle_btn = lambda icon, tooltip, on_click=None, disabled=False: ft.Container(  # noqa: E731
            content=ft.Icon(icon, color="#61789c", size=18),
            width=40, height=40,
            border_radius=9999,
            bgcolor=ft.Colors.with_opacity(0.5, "#f8fafc"),
            border=ft.border.all(1, ft.Colors.with_opacity(0.6, "#e2e8f0")),
            alignment=ft.Alignment(0, 0),
            tooltip=tooltip,
            on_click=None if disabled else on_click,
            ink=not disabled,
            opacity=0.45 if disabled else 1.0,
        )
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(expand=True),
                    search_box,
                    circle_btn(ft.Icons.NOTIFICATIONS_OUTLINED, "暂无新通知", disabled=True),
                    circle_btn(
                        ft.Icons.SETTINGS_OUTLINED, "设置",
                        on_click=lambda _: self._page.go("/settings"),
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=80,
            bgcolor=ft.Colors.with_opacity(0.8, "#ffffff"),
            border=ft.border.only(
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.5, "#e2e8f0")),
            ),
            padding=ft.padding.symmetric(horizontal=32),
        )

    # ── 主体 ──────────────────────────────────────────────────
    def _build_body(self) -> ft.Control:
        return ft.Container(
            expand=True,
            bgcolor="#f4f6ff",
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self._build_header(),
                                ft.Container(height=24),
                                self._build_stats(),
                                ft.Container(height=24),
                                self._build_table(),
                                ft.Container(height=24),
                                self._build_tip_card(),
                                ft.Container(height=32),
                            ],
                            spacing=0,
                        ),
                        padding=ft.padding.all(32),
                    ),
                ],
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    # ── 标题区（高 64px）──────────────────────────────────────
    def _build_header(self) -> ft.Control:
        return ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text(
                            "最近操作", size=30,
                            weight=ft.FontWeight.W_800,
                            color="#162f50",
                            font_family="WenQuanYi Zen Hei",
                        ),
                        ft.Text(
                            "管理并回顾您在过去 30 天内的所有文件处理记录。",
                            size=16, weight=ft.FontWeight.W_400,
                            color="#455c7f",
                            font_family="WenQuanYi Zen Hei",
                        ),
                    ],
                    spacing=4,
                    tight=True,
                ),
                ft.Container(expand=True),
                # 导出记录按钮
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.FILE_DOWNLOAD_OUTLINED, color="#455c7f", size=16),
                            ft.Text(
                                "导出记录", size=14,
                                weight=ft.FontWeight.W_700, color="#455c7f",
                                font_family="42dot Sans",
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                    ),
                    bgcolor="#cbdeff",
                    border_radius=12,
                    padding=ft.padding.symmetric(horizontal=20, vertical=10),
                    on_click=self._export_history,
                    ink=True,
                    tooltip="导出为 CSV",
                ),
                ft.Container(width=12),
                # 清空历史按钮
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DELETE_OUTLINE, color="#ffffff", size=16),
                            ft.Text(
                                "清空历史", size=14,
                                weight=ft.FontWeight.W_700, color="#ffffff",
                                font_family="42dot Sans",
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                    ),
                    bgcolor="#005f98",
                    border_radius=12,
                    padding=ft.padding.symmetric(horizontal=20, vertical=10),
                    shadow=ft.BoxShadow(
                        blur_radius=10, spread_radius=-2,
                        color=ft.Colors.with_opacity(0.25, "#005f98"),
                        offset=ft.Offset(0, 4),
                    ),
                    on_click=self._clear_history,
                    ink=True,
                    tooltip="清空所有历史记录",
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.END,
        )

    # ── Dashboard 4 张统计卡片（高 91px）────────────────────────
    def _build_stats(self) -> ft.Control:
        cards = [
            self._build_stat_card(
                "今日处理", "#005f98",
                self._stat_today_value, self._stat_today_unit,
                bg=ft.Colors.with_opacity(0.1, "#2aa7ff"), border="#005f98",
            ),
            self._build_stat_card(
                "节省空间", "#6b1ef3",
                self._stat_saved_value, self._stat_saved_unit,
                bg=ft.Colors.with_opacity(0.2, "#d9caff"), border="#6b1ef3",
            ),
            self._build_stat_card(
                "转换成功率", "#006571",
                self._stat_rate_value, self._stat_rate_unit,
                bg=ft.Colors.with_opacity(0.1, "#00e3fd"), border="#006571",
            ),
            self._build_stat_card(
                "云端占用", "#455c7f",
                self._stat_cloud_value, self._stat_cloud_unit,
                bg="#d5e3ff", border="#61789c",
            ),
        ]
        return ft.Row(controls=cards, spacing=16)

    def _build_stat_card(
        self, label: str, label_color: str,
        value: ft.Text, unit: ft.Text,
        bg: str, border: str,
    ) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        label, size=10, weight=ft.FontWeight.W_900,
                        color=label_color,
                        font_family="WenQuanYi Zen Hei",
                    ),
                    ft.Row(
                        controls=[value, unit],
                        spacing=2,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        tight=True,
                    ),
                ],
                spacing=8,
                tight=True,
            ),
            bgcolor=bg,
            border=ft.border.all(1, ft.Colors.with_opacity(0.3, border)),
            border_radius=16,
            padding=ft.padding.all(20),
            height=91,
            expand=True,
        )

    # ── 数据表格（圆角 24）────────────────────────────────────
    def _build_table(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._build_table_header(),
                    self._rows_column,
                    self._empty_hint,
                    self._build_pagination(),
                ],
                spacing=0,
            ),
            bgcolor="#ffffff",
            border_radius=24,
            shadow=ft.BoxShadow(
                blur_radius=4, spread_radius=0,
                color=ft.Colors.with_opacity(0.04, "#000000"),
                offset=ft.Offset(0, 2),
            ),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

    def _build_table_header(self) -> ft.Control:
        def cell(text: str, width: int | None = None, expand: bool = False) -> ft.Container:
            return ft.Container(
                content=ft.Text(
                    text, size=11, weight=ft.FontWeight.W_900,
                    color="#455c7f", font_family="42dot Sans",
                ),
                width=width, expand=expand,
                padding=ft.padding.only(left=24, top=20, right=24, bottom=22),
            )

        return ft.Container(
            content=ft.Row(
                controls=[
                    cell("文件名", width=241),
                    cell("操作类型", width=151),
                    cell("状态", width=92),
                    cell("日期", width=159),
                    cell("大小", width=105),
                    cell("耗时", width=77),
                    cell("操作", expand=True),
                ],
                spacing=0,
            ),
            bgcolor=ft.Colors.with_opacity(0.5, "#ebf1ff"),
            height=55,
        )

    # ── 分页器（高 64px）───────────────────────────────────────
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
            bgcolor=ft.Colors.with_opacity(0.3, "#ebf1ff"),
            height=64,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
        )

    # ── 效率提示卡片 ──────────────────────────────────────────
    def _build_tip_card(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.LIGHTBULB_OUTLINE, color="#005f98", size=22,
                        ),
                        width=48, height=48,
                        border_radius=9999,
                        bgcolor=ft.Colors.with_opacity(0.2, "#005f98"),
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "效率提示", size=16,
                                weight=ft.FontWeight.W_700, color="#00253f",
                                font_family="42dot Sans",
                            ),
                            ft.Text(
                                "对于处理失败的大型视频文件，可能因为高峰期同时处理文件过多，您可选择稍后重试！",
                                size=14, weight=ft.FontWeight.W_500,
                                color="#455c7f", font_family="42dot Sans",
                            ),
                        ],
                        spacing=4,
                        tight=True,
                        expand=True,
                    ),
                ],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.1, "#2aa7ff"),
            border=ft.border.all(1, ft.Colors.with_opacity(0.2, "#2aa7ff")),
            border_radius=16,
            padding=ft.padding.all(24),
        )

    # ── 数据加载与过滤 ────────────────────────────────────────
    def _reload_from_service(self) -> None:
        self._all_tasks = history_service.get_recent_tasks(limit=500)
        self._apply_filter()
        self._refresh_stats()
        if self._topbar.page:
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
            self._page_btn(ft.Icons.CHEVRON_LEFT, None,
                           disabled=self._current_page <= 1,
                           on_click=lambda _: self._goto_page(self._current_page - 1)),
        )
        # 页码（最多 5 个，含省略号）
        for page_num in self._build_page_numbers(total_pages):
            if page_num == "...":
                self._pagination_buttons.controls.append(
                    ft.Container(
                        content=ft.Text(
                            "...", size=12, color="#455c7f",
                            font_family="Plus Jakarta Sans",
                            weight=ft.FontWeight.W_500,
                        ),
                        width=32, height=32, alignment=ft.Alignment(0, 0),
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
            self._page_btn(ft.Icons.CHEVRON_RIGHT, None,
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
            content = ft.Icon(
                icon,
                color="#94a3b8" if disabled else "#455c7f",
                size=14,
            )
        else:
            content = ft.Text(
                label or "", size=12,
                color="#ffffff" if active else "#455c7f",
                font_family="Plus Jakarta Sans",
                weight=ft.FontWeight.W_700 if active else ft.FontWeight.W_500,
                text_align=ft.TextAlign.CENTER,
            )
        return ft.Container(
            content=content,
            width=32, height=32,
            bgcolor="#005f98" if active else "transparent",
            border=None if active else ft.border.all(1, ft.Colors.with_opacity(0.5, "#e2e8f0")),
            border_radius=8,
            alignment=ft.Alignment(0, 0),
            on_click=None if (disabled or active) else on_click,
            ink=not (disabled or active),
            opacity=0.4 if disabled else 1.0,
        )

    def _goto_page(self, page_num: int) -> None:
        total_pages = max(1, (len(self._filtered_tasks) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        self._current_page = max(1, min(page_num, total_pages))
        self._render_rows()
        self._render_pagination()
        if self._topbar.page:
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

        icon_bg, icon_color, icon_name, module_label = _MODULE_META.get(
            module, ("#d5e3ff", "#162f50", ft.Icons.DESCRIPTION, module or "其他"),
        )
        action_label = _ACTION_LABELS.get(action, module_label)
        date_str = self._format_date(created_at)
        duration_str = "—" if status != "success" or duration_s is None else self._format_duration(duration_s)

        # 文件名列：图标 + 文件名
        filename_col = ft.Container(
            width=241,
            padding=ft.padding.only(left=24, right=12, top=14, bottom=14),
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon_name, color=icon_color, size=18),
                        width=40, height=40,
                        bgcolor=icon_bg,
                        border_radius=8,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Container(
                        content=ft.Text(
                            input_desc, size=14,
                            weight=ft.FontWeight.W_700, color="#162f50",
                            font_family="Plus Jakarta Sans",
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        # 操作类型列：药丸形标签
        action_pill = ft.Container(
            width=151,
            padding=ft.padding.only(left=24, right=12, top=14, bottom=14),
            content=ft.Container(
                content=ft.Text(
                    action_label, size=12,
                    weight=ft.FontWeight.W_700, color="#455c7f",
                    font_family="WenQuanYi Zen Hei",
                ),
                bgcolor="#dee9ff",
                border_radius=9999,
                padding=ft.padding.symmetric(horizontal=12, vertical=4),
                alignment=ft.Alignment(-1, 0),
            ),
            alignment=ft.Alignment(-1, 0),
        )

        # 状态列：圆点 + 文字
        if status == "success":
            dot_color, status_text_color, status_label = "#10b981", "#059669", "成功"
        elif status == "failed":
            dot_color, status_text_color, status_label = "#b31b25", "#b31b25", "失败"
        elif status == "cancelled":
            dot_color, status_text_color, status_label = "#f59e0b", "#b45309", "已取消"
        else:  # running
            dot_color, status_text_color, status_label = "#005f98", "#005f98", "处理中"

        status_col = ft.Container(
            width=92,
            padding=ft.padding.only(left=24, right=12, top=14, bottom=14),
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=8, height=8,
                        bgcolor=dot_color,
                        border_radius=9999,
                    ),
                    ft.Text(
                        status_label, size=12,
                        weight=ft.FontWeight.W_700, color=status_text_color,
                        font_family="42dot Sans",
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
        )

        # 日期列
        date_col = ft.Container(
            width=159,
            padding=ft.padding.only(left=24, right=12, top=14, bottom=14),
            content=ft.Text(
                date_str, size=12,
                weight=ft.FontWeight.W_400, color="#455c7f",
                font_family="Plus Jakarta Sans",
            ),
        )
        # 大小列（无数据源，占位 "—"）
        size_col = ft.Container(
            width=105,
            padding=ft.padding.only(left=24, right=12, top=14, bottom=14),
            content=ft.Text(
                "—", size=12,
                weight=ft.FontWeight.W_500, color="#455c7f",
                font_family="Plus Jakarta Sans",
            ),
        )
        # 耗时列
        duration_col = ft.Container(
            width=77,
            padding=ft.padding.only(left=24, right=12, top=14, bottom=14),
            content=ft.Text(
                duration_str, size=12,
                weight=ft.FontWeight.W_400, color="#455c7f",
                font_family="Plus Jakarta Sans",
            ),
        )
        # 操作列
        action_buttons: list[ft.Control] = []
        if status == "success" and output_dir:
            action_buttons.append(
                ft.Container(
                    content=ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, color="#00a3ff", size=16),
                    width=34, height=28,
                    bgcolor=ft.Colors.with_opacity(0.1, "#00a3ff"),
                    border_radius=8,
                    alignment=ft.Alignment(0, 0),
                    on_click=lambda _, d=output_dir: self._open_dir(d),
                    ink=True,
                    tooltip="打开输出目录",
                ),
            )
        # 删除按钮
        task_id = task.get("id")
        action_buttons.append(
            ft.Container(
                content=ft.Icon(ft.Icons.DELETE_OUTLINE, color="#00a3ff", size=16),
                width=29, height=29,
                bgcolor=ft.Colors.with_opacity(0.1, "#00a3ff"),
                border_radius=8,
                alignment=ft.Alignment(0, 0),
                on_click=lambda _, tid=task_id: self._delete_row(tid),
                ink=True,
                tooltip="删除此记录",
            ),
        )
        action_col = ft.Container(
            expand=True,
            padding=ft.padding.only(left=24, right=24, top=14, bottom=14),
            content=ft.Row(
                controls=action_buttons,
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
        )

        row = ft.Container(
            content=ft.Row(
                controls=[filename_col, action_pill, status_col, date_col,
                          size_col, duration_col, action_col],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            border=(
                None if is_last
                else ft.border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.5, "#e2e8f0")))
            ),
        )
        return row

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

        self._stat_today_value.value = str(today_count)
        self._stat_today_unit.value = "个文件"
        self._stat_rate_value.value = f"{rate:.1f}"
        self._stat_rate_unit.value = "%"
        # 节省空间 / 云端占用：无数据源，占位
        self._stat_saved_value.value = "—"
        self._stat_saved_unit.value = ""
        self._stat_cloud_value.value = "—"
        self._stat_cloud_unit.value = ""

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
            s = float(seconds)
        except (TypeError, ValueError):
            return "—"
        if s < 60:
            return f"{s:.1f}s"
        m, r = divmod(s, 60)
        return f"{int(m)}m{int(r)}s"

    # ── 交互：搜索 / 清空 / 删除 / 打开 / 导出 ─────────────────
    def _on_search_change(self, e: ft.ControlEvent) -> None:
        self._search_keyword = (e.control.value or "")
        self._current_page = 1
        self._apply_filter()
        if self._topbar.page:
            self.update()

    def _clear_history(self, _) -> None:
        history_service.clear_history()
        show_toast(self._page, "已清空所有历史记录")
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
            show_toast(self._page, f"删除失败：{exc}", color="#b31b25")
            return
        show_toast(self._page, "已删除该记录")
        self._reload_from_service()

    def _open_dir(self, path_str: str) -> None:
        if not path_str:
            return
        p = Path(path_str)
        if not p.exists():
            show_toast(self._page, "目录不存在或已被移动", color="#b31b25")
            return
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(p)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except OSError as exc:
            show_toast(self._page, f"打开失败：{exc}", color="#b31b25")

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
            show_toast(self._page, f"导出失败：{exc}", color="#b31b25")
            return
        show_toast(self._page, f"已导出 {len(self._filtered_tasks)} 条记录到 {csv_path.name}")
