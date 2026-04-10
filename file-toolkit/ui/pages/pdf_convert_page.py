"""PDF↔Office 转换操作页"""
import flet as ft


class PdfConvertPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/pdf/to-office")
        self.controls = [
            ft.Text("PDF↔Office 转换操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
