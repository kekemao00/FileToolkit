"""图片水印操作页"""
import flet as ft


class ImageWatermarkPage(ft.Column):
    """图片水印操作页"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True)
        self._page = page
        self.controls = [
            ft.Container(
                content=ft.Text(
                    "图片水印操作页 — 待实现",
                    style=ft.TextThemeStyle.BODY_LARGE,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                padding=ft.padding.all(24),
            ),
        ]
