"""PDF 工具集列表页"""
import flet as ft

from ui.components.action_card import ActionCard


class PdfPage(ft.Column):
    """PDF 工具集 — 6 张功能入口卡片"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self.spacing = 0
        self.controls = [
            self._build_header(),
            self._build_grid(),
        ]

    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "📄 PDF 工具",
                        style=ft.TextThemeStyle.HEADLINE_MEDIUM,
                        font_family="Manrope",
                        weight=ft.FontWeight.W_600,
                    ),
                    ft.Text(
                        "分割 · 合并 · 压缩 · Office 互转",
                        size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=4,
            ),
            padding=ft.padding.only(left=28, top=28, right=28, bottom=20),
        )

    def _build_grid(self) -> ft.Control:
        items = [
            (ft.Icons.CONTENT_CUT,    "PDF 分割",      "按页数 / 范围 / 每页单独",  "/pdf/split"),
            (ft.Icons.MERGE,          "PDF 合并",      "多文件合并，支持拖拽排序",  "/pdf/merge"),
            (ft.Icons.COMPRESS,       "PDF 压缩",      "高 / 中 / 低三档质量",    "/pdf/compress"),
            (ft.Icons.SWAP_HORIZ,     "PDF 转 Office", "转 Word / Excel / PPT",  "/pdf/to-office"),
            (ft.Icons.PICTURE_AS_PDF, "Office 转 PDF", "Word / Excel / PPT → PDF","/pdf/from-office"),
            (ft.Icons.DOCUMENT_SCANNER,"OCR 识别",     "扫描件转可编辑文字（联网）","/pdf/ocr"),
        ]
        return ft.Container(
            content=ft.ResponsiveRow(
                controls=[
                    ft.Column(
                        col={"xs": 12, "sm": 6, "lg": 4},
                        controls=[
                            ActionCard(
                                icon=icon,
                                title=title,
                                subtitle=subtitle,
                                on_click=lambda _, r=route: self._page.go(r),
                                icon_color=ft.Colors.PRIMARY,
                            )
                        ],
                    )
                    for icon, title, subtitle, route in items
                ],
                spacing=12,
                run_spacing=12,
            ),
            padding=ft.padding.symmetric(horizontal=28, vertical=8),
        )
