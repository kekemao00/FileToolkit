"""设置页"""
import flet as ft


class SettingsPage(ft.View):
    def __init__(self) -> None:
        super().__init__(route="/settings")
        self.controls = [
            ft.Text("设置页 — 待实现", style=ft.TextThemeStyle.BODY_LARGE),
        ]
