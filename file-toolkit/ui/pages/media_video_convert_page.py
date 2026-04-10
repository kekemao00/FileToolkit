"""视频格式转换操作页"""
import flet as ft


class VideoConvertPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/media/video-convert")
        self.controls = [
            ft.Text("视频格式转换操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
