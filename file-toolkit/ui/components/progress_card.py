"""进度展示卡片（确定/不确定进度，取消按钮）"""
import flet as ft


class ProgressCard(ft.UserControl):
    """进度展示卡片（确定/不确定进度，取消按钮）"""

    def build(self) -> ft.Control:
        raise NotImplementedError
