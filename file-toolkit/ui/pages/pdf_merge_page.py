"""PDF 合并操作页"""
import flet as ft


class PdfMergePage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/pdf/merge")
        self.controls = [
            ft.Text("PDF 合并操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
