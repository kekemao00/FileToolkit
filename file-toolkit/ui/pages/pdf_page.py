"""PDF 工具集列表"""
import flet as ft


class PdfPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/pdf")
        self.controls = [
            ft.Text("PDF 工具集列表 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
