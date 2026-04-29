"""最近操作 / 历史记录页"""
import flet as ft

from services import history_service


_STATUS_COLORS = {
    "success":   ("#d1fae5", "#047857"),
    "failed":    ("#fee2e2", "#b91c1c"),
    "cancelled": ("#fef9c3", "#92400e"),
    "running":   ("#dee9ff", "#005f98"),
}

_STATUS_LABELS = {
    "success":   "已完成",
    "failed":    "失败",
    "cancelled": "已取消",
    "running":   "处理中",
}

_MODULE_META = {
    "PDF":     ("#fee2e2", ft.Icons.PICTURE_AS_PDF),
    "IMAGE":   ("#dcfce7", ft.Icons.IMAGE),
    "MEDIA":   ("#f3e8ff", ft.Icons.MOVIE),
    "ARCHIVE": ("#dbeafe", ft.Icons.FOLDER_ZIP),
    "OCR":     ("#cffafe", ft.Icons.DOCUMENT_SCANNER),
}


class HistoryPage(ft.Column):
    """完整历史记录列表，带筛选"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._filter = "all"

        self._rows = ft.Column(spacing=0)
        self._empty_hint = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.HISTORY, size=48, color="#94a3b8"),
                    ft.Text("暂无历史记录", color="#455c7f", size=14, font_family="Manrope"),
                    ft.Text("完成第一次文件处理后，这里会显示记录", color="#94a3b8", size=12, font_family="Manrope"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.padding.symmetric(vertical=40),
            alignment=ft.Alignment(0, 0),
        )

        self.controls = [
            self._build_header(),
            self._build_filters(),
            self._build_table(),
        ]
        self._load_data()

    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.HISTORY, color="#005f98", size=24),
                        width=48,
                        height=48,
                        bgcolor="#dee9ff",
                        border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "最近操作",
                                size=24,
                                weight=ft.FontWeight.W_600,
                                color="#162f50",
                                font_family="Manrope",
                            ),
                            ft.Text(
                                "查看所有文件处理历史记录",
                                size=14,
                                color="#455c7f",
                                font_family="Manrope",
                            ),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=40, top=32, right=40, bottom=16),
        )

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
                    label,
                    size=13,
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

    def _build_table(self) -> ft.Control:
        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(content=ft.Text("文件名", size=12, color="#455c7f", font_family="Manrope"), expand=True),
                    ft.Container(content=ft.Text("类型", size=12, color="#455c7f", font_family="Manrope"), width=96),
                    ft.Container(content=ft.Text("状态", size=12, color="#455c7f", font_family="Manrope"), width=120),
                    ft.Container(content=ft.Text("时间", size=12, color="#455c7f", font_family="Manrope"), width=140),
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
            border_radius=16,
            padding=ft.padding.all(24),
            margin=ft.margin.only(left=40, right=40, top=16, bottom=40),
            shadow=ft.BoxShadow(blur_radius=1, color=ft.Colors.with_opacity(0.05, "#000000"), offset=ft.Offset(0, 1)),
        )

    def _load_data(self) -> None:
        tasks = history_service.get_recent_tasks(limit=50)
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
        status_bg, status_color = _STATUS_COLORS.get(status, ("#dee9ff", "#005f98"))
        status_label = _STATUS_LABELS.get(status, status)
        module = task.get("module", "").upper()
        action = task.get("action", "")
        input_desc = task.get("input_desc", "")
        created_at = task.get("created_at", "")[:16] if task.get("created_at") else ""
        icon_bg, icon_name = _MODULE_META.get(module, ("#dee9ff", ft.Icons.DESCRIPTION))

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(icon_name, color="#162f50", size=14),
                                    width=32,
                                    height=32,
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
                                            color="#162f50",
                                            font_family="Manrope",
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Text(
                                            action,
                                            size=11,
                                            color="#455c7f",
                                            font_family="Manrope",
                                        ),
                                    ],
                                    spacing=2,
                                    tight=True,
                                    expand=True,
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(action, size=12, color="#455c7f", font_family="Manrope"),
                        width=96,
                    ),
                    ft.Container(
                        content=ft.Container(
                            content=ft.Text(status_label, size=11, color=status_color, font_family="Manrope"),
                            bgcolor=status_bg,
                            border_radius=9999,
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        ),
                        width=120,
                    ),
                    ft.Container(
                        content=ft.Text(created_at, size=12, color="#455c7f", font_family="Manrope"),
                        width=140,
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            border=ft.border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.5, "#dee9ff"))),
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
