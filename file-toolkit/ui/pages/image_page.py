"""图片工具集列表页 — 基于 Figma 设计稿风格"""
import flet as ft


_TOOLS = [
    {
        "icon": ft.Icons.TRANSFORM,
        "title": "格式转换",
        "desc": "PNG / JPG / WebP / BMP 互转",
        "icon_bg": "#eff6ff",
        "icon_color": "#2563eb",
        "route": "/image/convert",
    },
    {
        "icon": ft.Icons.COMPRESS,
        "title": "图片压缩",
        "desc": "无损 / 有损压缩，批量处理",
        "icon_bg": "#f0fdf4",
        "icon_color": "#16a34a",
        "route": "/image/compress",
    },
    {
        "icon": ft.Icons.BRANDING_WATERMARK,
        "title": "添加水印",
        "desc": "文字 / 图片水印，自定义位置",
        "icon_bg": "#faf5ff",
        "icon_color": "#9333ea",
        "route": "/image/watermark",
    },
    {
        "icon": ft.Icons.DRIVE_FILE_RENAME_OUTLINE,
        "title": "批量重命名",
        "desc": "按规则批量重命名图片文件",
        "icon_bg": "#fff7ed",
        "icon_color": "#ea580c",
        "route": "/image/rename",
    },
]


class ImagePage(ft.Column):
    """图片工具集 — 卡片网格"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self.controls = [
            self._build_header(),
            self._build_grid(),
        ]

    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.IMAGE, color="#16a34a", size=24),
                        width=48,
                        height=48,
                        bgcolor="#f0fdf4",
                        border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "图片工具",
                                size=24,
                                weight=ft.FontWeight.W_600,
                                color="#162f50",
                                font_family="Manrope",
                            ),
                            ft.Text(
                                "格式转换 · 压缩 · 水印 · 批量重命名",
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

    def _build_grid(self) -> ft.Control:
        return ft.Container(
            content=ft.ResponsiveRow(
                controls=[
                    ft.Column(
                        col={"xs": 12, "sm": 6, "lg": 6},
                        controls=[self._build_card(t)],
                    )
                    for t in _TOOLS
                ],
                spacing=16,
                run_spacing=16,
            ),
            padding=ft.padding.symmetric(horizontal=40, vertical=8),
        )

    def _build_card(self, tool: dict) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(tool["icon"], color=tool["icon_color"], size=24),
                        width=48,
                        height=48,
                        bgcolor=tool["icon_bg"],
                        border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                tool["title"],
                                size=15,
                                weight=ft.FontWeight.W_600,
                                color="#162f50",
                                font_family="Manrope",
                            ),
                            ft.Text(
                                tool["desc"],
                                size=12,
                                color="#455c7f",
                                font_family="Manrope",
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=18, color="#94a3b8"),
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
            ink=True,
            on_click=lambda _, r=tool["route"]: self._page.go(r),
            on_hover=self._on_card_hover,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    @staticmethod
    def _on_card_hover(e: ft.ControlEvent) -> None:
        c = e.control
        if e.data == "true":
            c.shadow = ft.BoxShadow(
                blur_radius=20,
                color=ft.Colors.with_opacity(0.08, "#004d64"),
                offset=ft.Offset(0, 8),
            )
            c.bgcolor = "#f8fafc"
        else:
            c.shadow = ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            )
            c.bgcolor = "#ffffff"
        c.update()
