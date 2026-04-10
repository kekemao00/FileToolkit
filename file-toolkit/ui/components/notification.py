"""通知封装（SnackBar success/warn/info，AlertDialog error）"""
import flet as ft


class Notification(ft.UserControl):
    """通知封装（SnackBar success/warn/info，AlertDialog error）"""

    def build(self) -> ft.Control:
        raise NotImplementedError
