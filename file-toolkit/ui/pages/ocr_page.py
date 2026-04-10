"""OCR 识别操作页（联网）"""
import flet as ft


class OcrPage(ft.Column):
    """OCR 识别操作页（联网）"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True)
        self._page = page
        self.controls = [
            ft.Container(
                content=ft.Text(
                    "OCR 识别操作页（联网） — 待实现",
                    style=ft.TextThemeStyle.BODY_LARGE,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                padding=ft.padding.all(24),
            ),
        ]
