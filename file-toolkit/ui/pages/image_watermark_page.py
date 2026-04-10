"""图片水印操作页"""
import flet as ft


class ImageWatermarkPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/image/watermark")
        self.controls = [
            ft.Text("图片水印操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
