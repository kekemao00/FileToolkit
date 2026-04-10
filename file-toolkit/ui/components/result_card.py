"""处理结果卡片（文件列表+打开目录+再次处理）"""
import flet as ft


class ResultCard(ft.UserControl):
    """处理结果卡片（文件列表+打开目录+再次处理）"""

    def build(self) -> ft.Control:
        raise NotImplementedError
