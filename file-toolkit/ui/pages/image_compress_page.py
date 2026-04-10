"""图片批量压缩操作页"""
import flet as ft


class ImageCompressPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/image/compress")
        self.controls = [
            ft.Text("图片批量压缩操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
