"""文件列表（含移除/拖拽排序）"""
import flet as ft


class FileList(ft.UserControl):
    """文件列表（含移除/拖拽排序）"""

    def build(self) -> ft.Control:
        raise NotImplementedError
