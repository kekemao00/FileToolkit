"""音视频工具集列表"""
import flet as ft


class MediaPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/media")
        self.controls = [
            ft.Text("音视频工具集列表 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
