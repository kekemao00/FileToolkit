"""OCR 识别操作页（联网）"""
import flet as ft


class OcrPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/pdf/ocr")
        self.controls = [
            ft.Text("OCR 识别操作页（联网） — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
