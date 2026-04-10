"""图片工具集列表"""
import flet as ft


class ImagePage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/image")
        self.controls = [
            ft.Text("图片工具集列表 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
