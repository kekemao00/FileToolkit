"""PDF↔Office 转换操作页"""
from typing import Literal

import flet as ft


class PdfConvertPage(ft.Column):
    """PDF 转 Office / Office 转 PDF 操作页（共用同一页面，mode 区分方向）"""

    def __init__(self, page: ft.Page, mode: Literal["to_office", "from_office"] = "to_office") -> None:
        super().__init__(expand=True)
        self._page = page
        self._mode = mode
        label = "PDF 转 Office" if mode == "to_office" else "Office 转 PDF"
        self.controls = [
            ft.Container(
                content=ft.Text(
                    f"{label} — 待实现",
                    style=ft.TextThemeStyle.BODY_LARGE,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                padding=ft.padding.all(24),
            ),
        ]
