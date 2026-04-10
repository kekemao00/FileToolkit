"""PDF 压缩操作页"""
import flet as ft


class PdfCompressPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/pdf/compress")
        self.controls = [
            ft.Text("PDF 压缩操作页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
