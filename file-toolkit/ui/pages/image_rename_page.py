"""批量重命名操作页"""
import flet as ft


class ImageRenamePage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/image/rename")
        self.controls = [
            ft.Text("批量重命名操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
