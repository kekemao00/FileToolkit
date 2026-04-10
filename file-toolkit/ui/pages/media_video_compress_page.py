"""视频压缩操作页"""
import flet as ft


class VideoCompressPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/media/video-compress")
        self.controls = [
            ft.Text("视频压缩操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
