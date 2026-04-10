"""PDF 压缩操作页"""
import flet as ft


class PdfCompressPage(ft.Column):
    """PDF 压缩操作页"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True)
        self._page = page
        self.controls = [
            ft.Container(
                content=ft.Text(
                    "PDF 压缩操作页 — 待实现",
                    style=ft.TextThemeStyle.BODY_LARGE,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                padding=ft.padding.all(24),
            ),
        ]
