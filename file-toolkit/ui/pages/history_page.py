"""最近操作 — 基于 Figma 设计稿 1:1590 的 1:1 复刻

布局：顶部栏 + 标题区 + Dashboard 统计卡片 + 完整数据表格
"""
import flet as ft

from services import history_service
from ui.components.top_bar import TopBar


_STATUS_COLORS = {
    "success":   ("#d1fae5", "#047857", "已完成"),
    "failed":    ("#fee2e2", "#b91c1c", "失败"),
    "cancelled": ("#fef9c3", "#92400e", "已取消"),
    "running":   ("#dee9ff", "#005f98", "处理中"),
}

_MODULE_META = {
    "PDF":     ("#fee2e2", ft.Icons.PICTURE_AS_PDF, "#dc2626"),
    "IMAGE":   ("#dcfce7", ft.Icons.IMAGE, "#16a34a"),
    "MEDIA":   ("#f3e8ff", ft.Icons.MOVIE, "#9333ea"),
    "ARCHIVE": ("#dbeafe", ft.Icons.FOLDER_ZIP, "#2563eb"),
    "OCR":     ("#cffafe", ft.Icons.DOCUMENT_SCANNER, "#0891b2"),
}


class HistoryPage(ft.Column):
    """最近操作 — Dashboard + 数据表格"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._filter = "all"
        self._all_tasks = history_service.get_recent_tasks(limit=50)

        self._rows = ft.Column(spacing=0)
        self._empty_hint = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.HISTORY, size=48, color="#94a3b8"),
                    ft.Text(
                        "暂无历史记录", color="#455c7f", size=14,
                        font_family="Manrope",
                    ),
                    ft.Text(
                        "完成第一次文件处理后，这里会显示记录",
                        color="#94a3b8", size=12, font_family="Manrope",
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.padding.symmetric(vertical=40),
            alignment=ft.Alignment(0, 0),
        )

        self._filter_btns = []

        self.controls = [
            TopBar(page),
            self._build_body(),
        ]
        self._load_data()

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
        total = len(self._all_tasks)
        success = sum(1 for t in self._all_tasks if t.get("status") == "success")

        return ft.Container(
            padding=ft.padding.only(left=40, right=40, top=32, bottom=8),
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                "最近操作", size=28,
                                weight=ft.FontWeight.W_500,
                                color="#162f50", font_family="Manrope",
                            ),
                            ft.Text(
                                f"共 {total} 条记录 · {success} 次成功处理",
                                size=14, color="#455c7f", font_family="Manrope",
                            ),
                        ],
                        spacing=4,
                    ),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.DOWNLOAD, color="#ffffff", size=14),
                                ft.Text(
                                    "导出报告", size=13,
                                    color="#ffffff", font_family="Manrope",
                                ),
                            ],
                            spacing=8,
                        ),
                        bgcolor="#005f98",
                        border_radius=12,
                        padding=ft.padding.symmetric(horizontal=20, vertical=10),
                        shadow=ft.BoxShadow(
                            blur_radius=10, spread_radius=-2,
                            color=ft.Colors.with_opacity(0.2, "#005f98"),
                            offset=ft.Offset(0, 4),
                        ),
                        ink=True,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
        )

    # ── Dashboard 统计卡片 ────────────────────────────────
    def _build_stats(self) -> ft.Control:
        total = len(self._all_tasks)
        success = sum(1 for t in self._all_tasks if t.get("status") == "success")
        failed = sum(1 for t in self._all_tasks if t.get("status") == "failed")
        rate = f"{int(success / total * 100)}%" if total > 0 else "0%"

        stats = [
            ("今日处理", str(total), ft.Icons.TRENDING_UP, "#005f98", "#dee9ff"),
            ("成功率", rate, ft.Icons.CHECK_CIRCLE_OUTLINE, "#047857", "#d1fae5"),
            ("失败任务", str(failed), ft.Icons.ERROR_OUTLINE, "#b91c1c", "#fee2e2"),
            ("常用工具", self._top_module(), ft.Icons.STAR_OUTLINE, "#9333ea", "#f3e8ff"),
        ]

        cards = []
        for label, value, icon, color, bg in stats:
            card = ft.Container(
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
                                    font_family="Manrope",
                                ),
                                ft.Text(
                                    value, size=22,
                                    weight=ft.FontWeight.BOLD,
                                    color="#162f50", font_family="Manrope",
                                ),
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
            cards.append(card)

        return ft.Container(
            content=ft.Row(controls=cards, spacing=16),
            padding=ft.padding.symmetric(horizontal=40, vertical=16),
        )

    def _top_module(self) -> str:
        counts: dict[str, int] = {}
        for t in self._all_tasks:
            m = t.get("module", "").upper()
            counts[m] = counts.get(m, 0) + 1
        if not counts:
            return "--"
        labels = {"PDF": "PDF", "IMAGE": "图片", "MEDIA": "音视频", "ARCHIVE": "压缩", "OCR": "OCR"}
        top = max(counts, key=counts.get)
        return labels.get(top, top)

    # ── 筛选标签 ──────────────────────────────────────────
    def _build_filters(self) -> ft.Control:
        filters = [
            ("all", "全部"),
            ("PDF", "PDF"),
            ("IMAGE", "图片"),
            ("MEDIA", "音视频"),
            ("ARCHIVE", "压缩"),
            ("OCR", "OCR"),
        ]
        self._filter_btns = []
        for key, label in filters:
            active = key == self._filter
            btn = ft.Container(
                content=ft.Text(
                    label, size=13,
                    color="#005f98" if active else "#455c7f",
                    font_family="Manrope",
                    weight=ft.FontWeight.W_500 if active else ft.FontWeight.NORMAL,
                ),
                bgcolor="#dee9ff" if active else "transparent",
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=16, vertical=8),
                on_click=lambda _, k=key: self._set_filter(k),
                ink=True,
                data=key,
            )
            self._filter_btns.append(btn)

        return ft.Container(
            content=ft.Row(controls=self._filter_btns, spacing=4),
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
                            "文件名", size=12, color="#455c7f",
                            font_family="Manrope",
                        ),
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "类型", size=12, color="#455c7f",
                            font_family="Manrope",
                        ),
                        width=96,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "状态", size=12, color="#455c7f",
                            font_family="Manrope",
                        ),
                        width=120,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "时间", size=12, color="#455c7f",
                            font_family="Manrope",
                        ),
                        width=140,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "操作", size=12, color="#455c7f",
                            font_family="Manrope",
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
    def _load_data(self) -> None:
        tasks = self._all_tasks
        if self._filter != "all":
            tasks = [t for t in tasks if t.get("module", "").upper() == self._filter]

        self._rows.controls.clear()
        if not tasks:
            self._empty_hint.visible = True
            return

        self._empty_hint.visible = False
        for task in tasks:
            self._rows.controls.append(self._build_row(task))

    def _build_row(self, task: dict) -> ft.Control:
        status = task.get("status", "success")
        status_bg, status_color, status_label = _STATUS_COLORS.get(
            status, ("#dee9ff", "#005f98", status),
        )
        module = task.get("module", "").upper()
        action = task.get("action", "")
        input_desc = task.get("input_desc", "")
        created_at = task.get("created_at", "")[:16] if task.get("created_at") else ""
        icon_bg, icon_name, icon_color = _MODULE_META.get(
            module, ("#dee9ff", ft.Icons.DESCRIPTION, "#005f98"),
        )
        output_dir = task.get("output_dir") or ""

        def _open_dir(_, d=output_dir):
            if d:
                import subprocess, sys
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", d])

        return ft.Container(
            content=ft.Row(
                controls=[
                    # 文件名列
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(
                                        icon_name, color=icon_color, size=14,
                                    ),
                                    width=32, height=32,
                                    bgcolor=icon_bg,
                                    border_radius=8,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            input_desc or f"{module} · {action}",
                                            size=14,
                                            weight=ft.FontWeight.W_500,
                                            color="#162f50", font_family="Manrope",
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Text(
                                            action, size=11, color="#455c7f",
                                            font_family="Manrope",
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
                            action, size=12, color="#455c7f", font_family="Manrope",
                        ),
                        width=96,
                    ),
                    # 状态列
                    ft.Container(
                        content=ft.Container(
                            content=ft.Text(
                                status_label, size=11, color=status_color,
                                font_family="Manrope",
                            ),
                            bgcolor=status_bg,
                            border_radius=9999,
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        ),
                        width=120,
                    ),
                    # 时间列
                    ft.Container(
                        content=ft.Text(
                            created_at, size=12, color="#455c7f",
                            font_family="Manrope",
                        ),
                        width=140,
                    ),
                    # 操作列
                    ft.Container(
                        content=ft.IconButton(
                            icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                            icon_color="#455c7f", icon_size=16,
                            tooltip="打开目录",
                            on_click=_open_dir,
                            visible=bool(output_dir),
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
            btn.bgcolor = "#dee9ff" if active else "transparent"
            text = btn.content
            text.color = "#005f98" if active else "#455c7f"
            text.weight = ft.FontWeight.W_500 if active else ft.FontWeight.NORMAL
        self._load_data()
        self.update()
