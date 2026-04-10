"""图片工具集列表"""
import flet as ft


class ImagePage(ft.Column):
    """图片工具集列表"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True)
        self._page = page
        self.controls = [
            ft.Container(
                content=ft.Text(
                    "图片工具集列表 — 待实现",
                    style=ft.TextThemeStyle.BODY_LARGE,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                padding=ft.padding.all(24),
            ),
        ]
