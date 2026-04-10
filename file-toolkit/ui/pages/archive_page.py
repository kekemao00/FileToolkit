"""压缩解压操作页（Tab 切换）"""
import flet as ft


class ArchivePage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/archive")
        self.controls = [
            ft.Text("压缩解压操作页（Tab 切换） — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
