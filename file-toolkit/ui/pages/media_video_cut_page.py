"""视频剪切操作页"""
import flet as ft


class VideoCutPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/media/video-cut")
        self.controls = [
            ft.Text("视频剪切操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
