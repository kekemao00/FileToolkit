"""图片格式转换操作页"""
import flet as ft


class ImageConvertPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/image/convert")
        self.controls = [
            ft.Text("图片格式转换操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
