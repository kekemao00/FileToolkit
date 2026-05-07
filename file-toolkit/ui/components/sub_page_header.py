"""
共享子页面 Header 组件 — 基于 Figma 设计稿

统一子页面的返回按钮 + 图标容器 + 标题样式。
替代之前的 emoji 标题 + ft.TextThemeStyle 方案。
"""
import flet as ft


class SubPageHeader(ft.Container):
    """
    子页面标题栏：← 返回 + 图标 + 标题

    参数：
        title: 页面标题
        icon: Material Icon 名称
        icon_color: 图标颜色
        icon_bg: 图标背景色
        on_back: 返回回调
    """

    def __init__(
        self,
        title: str,
        icon: str,
        icon_color: str,
        icon_bg: str,
        on_back: callable,
    ) -> None:
        super().__init__(
            padding=ft.padding.only(left=32, top=24, right=32, bottom=16),
            content=ft.Row(
                controls=[
                    ft.IconButton(
                        ft.Icons.ARROW_BACK,
                        on_click=lambda _: on_back(),
                        icon_color="#455c7f",
                    ),
                    ft.Container(
                        content=ft.Icon(icon, color=icon_color, size=20),
                        width=40,
                        height=40,
                        bgcolor=icon_bg,
                        border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        title,
                        size=20,
                        weight=ft.FontWeight.W_600,
                        color="#162f50",
                        font_family="42dot Sans",
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
