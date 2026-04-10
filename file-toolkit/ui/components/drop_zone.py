"""文件拖拽区域（5种状态：IDLE/DRAG_HOVER/FILE_SELECTED/ERROR）"""
import flet as ft


class DropZone(ft.UserControl):
    """文件拖拽区域（5种状态：IDLE/DRAG_HOVER/FILE_SELECTED/ERROR）"""

    def build(self) -> ft.Control:
        raise NotImplementedError
