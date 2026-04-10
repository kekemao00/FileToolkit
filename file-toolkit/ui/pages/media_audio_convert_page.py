"""音频格式转换操作页"""
import flet as ft


class AudioConvertPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/media/audio-convert")
        self.controls = [
            ft.Text("音频格式转换操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
