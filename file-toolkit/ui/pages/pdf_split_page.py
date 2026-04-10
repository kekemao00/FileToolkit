"""PDF 分割操作页"""
import flet as ft


class PdfSplitPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/pdf/split")
        self.controls = [
            ft.Text("PDF 分割操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
