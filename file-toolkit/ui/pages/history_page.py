"""最近操作 — 基于 Figma 风格 1:1 还原

布局：顶部栏 + 标题区 + Dashboard 统计卡片 + 筛选按钮组 + 完整数据表格
遵循核心模式的视觉风格（色值、字体、间距一致）。
"""
import subprocess
import sys
from pathlib import Path

import flet as ft

from services import history_service

_STATUS_COLORS = {
    "success":   ("#d1fae5", "#047857", "已完成"),
    "failed":    ("#fee2e2", "#b91c1c", "失败"),
    "cancelled": ("#fef9c3", "#92400e", "已取消"),
    "running":   ("#dee9ff", "#005f98", "处理中"),
}

_MODULE_META = {
    "PDF":     ("#fee2e2", ft.Icons.PICTURE_AS_PDF, "#dc2626", "PDF"),
    "IMAGE":   ("#dcfce7", ft.Icons.IMAGE, "#16a34a", "图片"),
    "MEDIA":   ("#f3e8ff", ft.Icons.MOVIE, "#9333ea", "音视频"),
    "ARCHIVE": ("#dbeafe", ft.Icons.FOLDER_ZIP, "#2563eb", "压缩"),
    "OCR":     ("#cffafe", ft.Icons.DOCUMENT_SCANNER, "#0891b2", "OCR"),
    "AI":      ("#ede9fe", ft.Icons.AUTO_AWESOME, "#7c3aed", "AI"),
}

_FILTERS = [
    ("all", "全部"),
    ("PDF", "PDF"),
    ("IMAGE", "图片"),
    ("MEDIA", "音视频"),
    ("ARCHIVE", "压缩"),
    ("OCR", "OCR"),
    ("AI", "AI"),
]


class HistoryPage(ft.Column):
    """最近操作 — Dashboard + 数据表格。"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._filter = "all"
        self._all_tasks: list[dict] = []

        self._rows = ft.Column(spacing=0)
        self._empty_hint = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.HISTORY, size=48, color="#94a3b8"),
                    ft.Text(
                        "暂无操作记录", color="#455c7f", size=14,
                        font_family="42dot Sans",
                    ),
                    ft.Text(
                        "完成第一次文件处理后，这里会显示记录",
                        color="#94a3b8", size=12, font_family="42dot Sans",
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.padding.symmetric(vertical=40),
            alignment=ft.Alignment(0, 0),
        )

        self._filter_btns: list[ft.Container] = []
        self._header_subtitle = ft.Text(
            "", size=14, color="#455c7f", font_family="42dot Sans",
        )
        self._stat_today = ft.Text(
            "0", size=22, weight=ft.FontWeight.BOLD,
            color="#162f50", font_family="42dot Sans",
        )
        self._stat_rate = ft.Text(
            "0%", size=22, weight=ft.FontWeight.BOLD,
            color="#162f50", font_family="42dot Sans",
        )
        self._stat_failed = ft.Text(
            "0", size=22, weight=ft.FontWeight.BOLD,
            color="#162f50", font_family="42dot Sans",
        )
        self._stat_top = ft.Text(
            "--", size=22, weight=ft.FontWeight.BOLD,
            color="#162f50", font_family="42dot Sans",
        )

        self._topbar = self._build_topbar()
        self.controls = [self._topbar, self._build_body()]
        self._reload_from_service()

    # ── 顶部栏 ────────────────────────────────────────────
    def _build_topbar(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.SEARCH, color="#94a3b8", size=15),
                                            ft.Container(
                                                content=ft.Text("搜索功能或指令...", size=13, color="#94a3b8"),
                                                padding=ft.padding.only(left=8),
                                                expand=True,
                                            ),
                                        ],
                                        spacing=0,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    width=288, height=54,
                                    bgcolor=ft.Colors.with_opacity(0.5, "#f8fafc"),
                                    border=ft.border.all(1, ft.Colors.with_opacity(0.6, "#e2e8f0")),
                                    border_radius=9999,
                                    padding=ft.padding.symmetric(horizontal=15),
                                    opacity=0.45,
                                    tooltip="搜索",
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.NOTIFICATIONS_OUTLINED,
                                    icon_color="#475569", icon_size=20,
                                    disabled=True, opacity=0.45,
                                    tooltip="通知",
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.SETTINGS_OUTLINED,
                                    icon_color="#475569", icon_size=20,
                                    on_click=lambda _: self._page.go("/settings"),
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=80,
            bgcolor="#ffffff",
            shadow=ft.BoxShadow(
                blur_radius=2, color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
            padding=ft.padding.symmetric(horizontal=32),
        )

    # ── 主体 ──────────────────────────────────────────────
    def _build_body(self) -> ft.Control:
        return ft.Container(
            expand=True,
            content=ft.Column(
                controls=[
                    self._build_header(),
                    self._build_stats(),
                    self._build_filters(),
                    self._build_table(),
                ],
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    # ── 标题区 ────────────────────────────────────────────
    def _build_header(self) -> ft.Control:
        return ft.Container(
            padding=ft.padding.only(left=40, right=40, top=32, bottom=8),
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                "最近操作", size=28,
                                weight=ft.FontWeight.W_500,
                                color="#162f50", font_family="42dot Sans",
                            ),
                            self._header_subtitle,
                        ],
                        spacing=4,
                    ),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.REFRESH, color="#455c7f", size=14),
                                ft.Text(
                                    "刷新", size=13,
                                    color="#455c7f", font_family="42dot Sans",
                                ),
                            ],
                            spacing=6,
                        ),
                        bgcolor="#f1f5f9",
                        border_radius=12,
                        padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        on_click=lambda _: self._reload_from_service(),
                        ink=True,
                        tooltip="重新读取",
                    ),
                    ft.Container(width=10),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.DELETE_OUTLINE, color="#ffffff", size=14),
                                ft.Text(
                                    "清空历史", size=13,
                                    color="#ffffff", font_family="42dot Sans",
                                ),
                            ],
                            spacing=6,
                        ),
                        bgcolor="#be123c",
                        border_radius=12,
                        padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        shadow=ft.BoxShadow(
                            blur_radius=10, spread_radius=-2,
                            color=ft.Colors.with_opacity(0.2, "#be123c"),
                            offset=ft.Offset(0, 4),
                        ),
                        on_click=self._clear_history,
                        ink=True,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
        )

    # ── Dashboard 统计卡片 ────────────────────────────────
    def _build_stats(self) -> ft.Control:
        def make_card(label: str, value_text: ft.Text, icon,
                      color: str, bg: str) -> ft.Container:
            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(icon, color=color, size=20),
                            width=44, height=44,
                            bgcolor=bg,
                            border_radius=12,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    label, size=11, color="#455c7f",
                                    font_family="42dot Sans",
                                ),
                                value_text,
                            ],
                            spacing=2, tight=True,
                        ),
                    ],
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#ffffff",
                border_radius=16,
                padding=ft.padding.all(20),
                shadow=ft.BoxShadow(
                    blur_radius=1,
                    color=ft.Colors.with_opacity(0.05, "#000000"),
                    offset=ft.Offset(0, 1),
                ),
                border=ft.border.all(1, "#f1f5f9"),
                expand=True,
            )

        cards = [
            make_card("累计处理", self._stat_today,
                      ft.Icons.TRENDING_UP, "#005f98", "#dee9ff"),
            make_card("成功率", self._stat_rate,
                      ft.Icons.CHECK_CIRCLE_OUTLINE, "#047857", "#d1fae5"),
            make_card("失败任务", self._stat_failed,
                      ft.Icons.ERROR_OUTLINE, "#b91c1c", "#fee2e2"),
            make_card("常用工具", self._stat_top,
                      ft.Icons.STAR_OUTLINE, "#9333ea", "#f3e8ff"),
        ]
        return ft.Container(
            content=ft.Row(controls=cards, spacing=16, wrap=True, run_spacing=16),
            padding=ft.padding.symmetric(horizontal=40, vertical=16),
        )

    # ── 筛选标签 ──────────────────────────────────────────
    def _build_filters(self) -> ft.Control:
        self._filter_btns = []
        for key, label in _FILTERS:
            active = key == self._filter
            btn = ft.Container(
                content=ft.Text(
                    label, size=13,
                    color="#ffffff" if active else "#455c7f",
                    font_family="42dot Sans",
                    weight=ft.FontWeight.W_500,
                ),
                bgcolor="#005f98" if active else "transparent",
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=16, vertical=8),
                on_click=lambda _, k=key: self._set_filter(k),
                ink=True,
                data=key,
            )
            self._filter_btns.append(btn)

        return ft.Container(
            content=ft.Row(
                controls=self._filter_btns, spacing=4, wrap=True, run_spacing=4,
            ),
            bgcolor="#f1f5f9",
            border_radius=10,
            padding=ft.padding.all(4),
            margin=ft.margin.symmetric(horizontal=40),
        )

    # ── 数据表格 ──────────────────────────────────────────
    def _build_table(self) -> ft.Control:
        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            "任务", size=12, color="#455c7f",
                            font_family="42dot Sans",
                        ),
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "类型", size=12, color="#455c7f",
                            font_family="42dot Sans",
                        ),
                        width=96,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "状态", size=12, color="#455c7f",
                            font_family="42dot Sans",
                        ),
                        width=100,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "时间", size=12, color="#455c7f",
                            font_family="42dot Sans",
                        ),
                        width=140,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "操作", size=12, color="#455c7f",
                            font_family="42dot Sans",
                            text_align=ft.TextAlign.RIGHT,
                        ),
                        width=80,
                    ),
                ],
                spacing=0,
            ),
            border=ft.border.only(bottom=ft.BorderSide(1, "#dee9ff")),
            padding=ft.padding.only(bottom=12),
        )

        return ft.Container(
            content=ft.Column(
                controls=[header, self._rows, self._empty_hint],
                spacing=0,
            ),
            bgcolor="#ffffff",
            border_radius=20,
            padding=ft.padding.all(24),
            margin=ft.margin.only(left=40, right=40, top=16, bottom=40),
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
        )

    # ── 数据加载 ──────────────────────────────────────────
    def _reload_from_service(self) -> None:
        self._all_tasks = history_service.get_recent_tasks(limit=50)
        self._refresh_stats()
        self._load_data()
        if self._topbar.page:
            self.update()

    def _refresh_stats(self) -> None:
        total = len(self._all_tasks)
        success = sum(1 for t in self._all_tasks
                      if t.get("status") == "success")
        failed = sum(1 for t in self._all_tasks
                     if t.get("status") == "failed")
        rate = f"{int(success / total * 100)}%" if total > 0 else "0%"

        self._header_subtitle.value = (
            f"共 {total} 条记录 · {success} 次成功处理"
        )
        self._stat_today.value = str(total)
        self._stat_rate.value = rate
        self._stat_failed.value = str(failed)
        self._stat_top.value = self._top_module()

    def _top_module(self) -> str:
        counts: dict[str, int] = {}
        for t in self._all_tasks:
            m = (t.get("module") or "").upper()
            if m:
                counts[m] = counts.get(m, 0) + 1
        if not counts:
            return "--"
        top = max(counts, key=counts.get)
        return _MODULE_META.get(top, (None, None, None, top))[3]

    def _load_data(self) -> None:
        tasks = self._all_tasks
        if self._filter != "all":
            tasks = [t for t in tasks
                     if (t.get("module") or "").upper() == self._filter]

        self._rows.controls.clear()
        self._empty_hint.visible = not tasks
        for task in tasks:
            self._rows.controls.append(self._build_row(task))

    def _build_row(self, task: dict) -> ft.Control:
        status = task.get("status", "success")
        status_bg, status_color, status_label = _STATUS_COLORS.get(
            status, ("#dee9ff", "#005f98", status),
        )
        module = (task.get("module") or "").upper()
        action = task.get("action") or ""
        input_desc = task.get("input_desc") or ""
        created_at = task.get("created_at") or ""
        created_at = created_at[:16] if created_at else ""
        icon_bg, icon_name, icon_color, module_label = _MODULE_META.get(
            module, ("#dee9ff", ft.Icons.DESCRIPTION, "#005f98", module or "其他"),
        )
        output_dir = task.get("output_dir") or ""

        return ft.Container(
            content=ft.Row(
                controls=[
                    # 任务描述列
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(icon_name, color=icon_color, size=14),
                                    width=32, height=32,
                                    bgcolor=icon_bg,
                                    border_radius=8,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            input_desc or f"{module_label} · {action}",
                                            size=14,
                                            weight=ft.FontWeight.W_500,
                                            color="#162f50", font_family="42dot Sans",
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Text(
                                            action, size=11, color="#455c7f",
                                            font_family="42dot Sans",
                                        ),
                                    ],
                                    spacing=2, tight=True, expand=True,
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        expand=True,
                    ),
                    # 类型列
                    ft.Container(
                        content=ft.Text(
                            module_label, size=12, color="#455c7f",
                            font_family="42dot Sans",
                        ),
                        width=96,
                    ),
                    # 状态列
                    ft.Container(
                        content=ft.Container(
                            content=ft.Text(
                                status_label, size=11, color=status_color,
                                font_family="42dot Sans",
                                weight=ft.FontWeight.W_500,
                            ),
                            bgcolor=status_bg,
                            border_radius=9999,
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        ),
                        width=100,
                    ),
                    # 时间列
                    ft.Container(
                        content=ft.Text(
                            created_at, size=12, color="#455c7f",
                            font_family="42dot Sans",
                        ),
                        width=140,
                    ),
                    # 操作列
                    ft.Container(
                        content=ft.IconButton(
                            icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                            icon_color="#455c7f", icon_size=16,
                            tooltip="打开输出目录" if output_dir else "无输出目录",
                            on_click=lambda _, d=output_dir: self._open_dir(d),
                            disabled=not output_dir,
                        ),
                        width=80,
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            border=ft.border.only(
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.5, "#dee9ff")),
            ),
            padding=ft.padding.symmetric(vertical=12),
        )

    def _set_filter(self, key: str) -> None:
        self._filter = key
        for btn in self._filter_btns:
            active = btn.data == key
            btn.bgcolor = "#005f98" if active else "transparent"
            text = btn.content
            text.color = "#ffffff" if active else "#455c7f"
            text.weight = ft.FontWeight.W_500
        self._load_data()
        self.update()

    def _clear_history(self, _) -> None:
        history_service.clear_history()
        self._show_snack("已清空所有历史记录")
        self._reload_from_service()

    def _open_dir(self, path_str: str) -> None:
        if not path_str:
            return
        p = Path(path_str)
        if not p.exists():
            self._show_snack("目录不存在或已被移动")
            return
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(p)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except OSError as exc:
            self._show_snack(f"打开失败：{exc}", color="#be123c")

    def _show_snack(self, msg: str, color: str = "#005f98") -> None:
        self._page.snack_bar = ft.SnackBar(
            content=ft.Text(msg), bgcolor=color, duration=2200,
        )
        self._page.snack_bar.open = True
        self._page.update()
