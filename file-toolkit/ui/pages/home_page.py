"""首页 — 快速入口 + 最近任务"""
import flet as ft


class HomePage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/")
        self.controls = [
            ft.Text("首页 — 快速入口 + 最近任务 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
