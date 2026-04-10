"""音频提取操作页"""
import flet as ft


class AudioExtractPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/media/audio-extract")
        self.controls = [
            ft.Text("音频提取操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
