"""AI 智能任务页 — 自然语言输入 + 任务列表"""
import flet as ft


_QUICK_ACTIONS = [
    {"icon": ft.Icons.PICTURE_AS_PDF, "label": "压缩这个 PDF", "color": "#dc2626", "bg": "#fef2f2"},
    {"icon": ft.Icons.IMAGE, "label": "批量转换图片为 WebP", "color": "#16a34a", "bg": "#f0fdf4"},
    {"icon": ft.Icons.MERGE, "label": "合并多个 PDF", "color": "#2563eb", "bg": "#eff6ff"},
    {"icon": ft.Icons.MOVIE, "label": "提取视频中的音频", "color": "#9333ea", "bg": "#faf5ff"},
    {"icon": ft.Icons.FOLDER_ZIP, "label": "打包这些文件", "color": "#ea580c", "bg": "#fff7ed"},
    {"icon": ft.Icons.DOCUMENT_SCANNER, "label": "识别图片中的文字", "color": "#0891b2", "bg": "#ecfeff"},
]


class AiTaskPage(ft.Column):
    """AI 智能任务：自然语言描述 → 自动匹配工具 → 执行"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page

        self._input_field = ft.TextField(
            hint_text="描述你想做的事情，例如：把桌面上的 3 个 PDF 合并成一个...",
            border_radius=16,
            multiline=True,
            min_lines=3,
            max_lines=5,
            on_submit=self._on_submit,
            border_color="#dee9ff",
            focused_border_color="#005f98",
        )

        self._send_btn = ft.FilledButton(
            "智能执行",
            icon=ft.Icons.AUTO_AWESOME,
            on_click=self._on_submit,
            style=ft.ButtonStyle(
                bgcolor="#005f98",
                color="#ffffff",
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.padding.symmetric(horizontal=24, vertical=12),
            ),
        )

        self._task_list = ft.Column(spacing=12)

        self.controls = [
            self._build_header(),
            self._build_input_section(),
            self._build_quick_actions(),
            self._build_task_section(),
        ]

    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.AUTO_AWESOME, color="#005f98", size=24),
                        width=48,
                        height=48,
                        bgcolor="#dee9ff",
                        border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "AI 智能任务",
                                size=24,
                                weight=ft.FontWeight.W_600,
                                color="#162f50",
                                font_family="Manrope",
                            ),
                            ft.Text(
                                "用自然语言描述任务，AI 自动匹配最佳工具",
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
            padding=ft.padding.only(left=40, top=32, right=40, bottom=24),
        )

    def _build_input_section(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._input_field,
                    ft.Row(
                        controls=[
                            ft.Container(expand=True),
                            self._send_btn,
                        ],
                    ),
                ],
                spacing=12,
            ),
            bgcolor="#ffffff",
            border_radius=16,
            padding=ft.padding.all(24),
            margin=ft.margin.symmetric(horizontal=40),
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
        )

    def _build_quick_actions(self) -> ft.Control:
        chips = []
        for action in _QUICK_ACTIONS:
            chip = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(action["icon"], color=action["color"], size=16),
                            width=32,
                            height=32,
                            bgcolor=action["bg"],
                            border_radius=8,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Text(
                            action["label"],
                            size=13,
                            color="#162f50",
                            font_family="Manrope",
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#ffffff",
                border=ft.border.all(1, "#e2e8f0"),
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                ink=True,
                on_click=lambda _, a=action: self._use_quick_action(a["label"]),
                on_hover=self._on_chip_hover,
                animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            )
            chips.append(chip)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "快捷指令",
                        size=16,
                        weight=ft.FontWeight.W_500,
                        color="#162f50",
                        font_family="Manrope",
                    ),
                    ft.Row(
                        controls=chips,
                        wrap=True,
                        spacing=10,
                        run_spacing=10,
                    ),
                ],
                spacing=16,
            ),
            padding=ft.padding.only(left=40, top=24, right=40, bottom=8),
        )

    def _build_task_section(self) -> ft.Control:
        empty_hint = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME, size=48, color="#94a3b8"),
                    ft.Text("暂无任务", color="#455c7f", size=14, font_family="Manrope"),
                    ft.Text(
                        "输入任务描述或点击快捷指令开始",
                        color="#94a3b8",
                        size=12,
                        font_family="Manrope",
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.padding.symmetric(vertical=40),
            alignment=ft.Alignment(0, 0),
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "任务列表",
                        size=16,
                        weight=ft.FontWeight.W_500,
                        color="#162f50",
                        font_family="Manrope",
                    ),
                    self._task_list,
                    empty_hint,
                ],
                spacing=16,
            ),
            bgcolor="#ffffff",
            border_radius=16,
            padding=ft.padding.all(24),
            margin=ft.margin.only(left=40, right=40, top=16, bottom=40),
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
        )

    def _use_quick_action(self, label: str) -> None:
        self._input_field.value = label
        self._input_field.update()

    def _on_submit(self, _) -> None:
        text = (self._input_field.value or "").strip()
        if not text:
            return
        self._page.snack_bar = ft.SnackBar(
            content=ft.Text("AI 任务解析功能即将上线，敬请期待"),
            bgcolor="#005f98",
        )
        self._page.snack_bar.open = True
        self._page.update()

    @staticmethod
    def _on_chip_hover(e: ft.ControlEvent) -> None:
        c = e.control
        if e.data == "true":
            c.bgcolor = "#f8fafc"
            c.border = ft.border.all(1, "#005f98")
        else:
            c.bgcolor = "#ffffff"
            c.border = ft.border.all(1, "#e2e8f0")
        c.update()
