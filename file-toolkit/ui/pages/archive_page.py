"""压缩解压操作页（Tab 切换）"""
import flet as ft


class ArchivePage(ft.Column):
    """压缩解压操作页（Tab 切换）"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True)
        self._page = page
        self.controls = [
            ft.Container(
                content=ft.Text(
                    "压缩解压操作页（Tab 切换） — 待实现",
                    style=ft.TextThemeStyle.BODY_LARGE,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                padding=ft.padding.all(24),
            ),
        ]
